"""
SEC filings (10-K / 10-Q) discovery and key-figure extraction.

Primary provider (if SEC_API_KEY is configured): sec-api.io, which offers a
convenient search + full-text extraction API.

Fallback provider (always available, no key required): the free public SEC
EDGAR APIs - https://data.sec.gov/. SEC requires every automated caller to
send a descriptive User-Agent identifying the application and a contact
address; this is read from settings and applied to every request. See
https://www.sec.gov/os/webmaster-faq#developers for the policy.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from cachetools import TTLCache

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.schemas import CompanyFinancialFacts, SecFiling, SecFilingsResponse
from app.utils.errors import (
    AllProvidersFailedError,
    DataProviderRateLimitError,
    DataProviderUnavailableError,
    NoDataFoundError,
)
from app.utils.retry import external_api_retry

logger = get_logger(__name__)

EDGAR_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik10}.json"
EDGAR_COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json"
EDGAR_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"

# The ticker -> CIK map changes rarely; cache it for a day.
_ticker_cik_cache: TTLCache = TTLCache(maxsize=1, ttl=86_400)
_filings_cache: TTLCache = TTLCache(maxsize=256, ttl=3_600)
_facts_cache: TTLCache = TTLCache(maxsize=256, ttl=3_600)

# Revenue/income/etc. can appear under several different XBRL tags
# depending on how a company reports; try each in priority order.
_XBRL_TAG_CANDIDATES = {
    "revenue_usd": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"],
    "net_income_usd": ["NetIncomeLoss", "ProfitLoss"],
    "total_assets_usd": ["Assets"],
    "total_liabilities_usd": ["Liabilities"],
    "cash_and_equivalents_usd": ["CashAndCashEquivalentsAtCarryingValue", "CashAndCashEquivalentsAtFairValue"],
    "eps_basic": ["EarningsPerShareBasic"],
}


class SecService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def _edgar_headers(self) -> dict:
        return {
            "User-Agent": self.settings.sec_edgar_user_agent,
            "Accept-Encoding": "gzip, deflate",
        }

    # ------------------------------------------------------------------
    # Ticker -> CIK resolution
    # ------------------------------------------------------------------
    async def resolve_cik(self, ticker: str) -> str:
        ticker = ticker.strip().upper()
        mapping = await self._get_ticker_cik_map()
        cik = mapping.get(ticker)
        if not cik:
            raise NoDataFoundError(ticker)
        return cik

    async def _get_ticker_cik_map(self) -> dict[str, str]:
        if "map" in _ticker_cik_cache:
            return _ticker_cik_cache["map"]

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.get(EDGAR_TICKER_MAP_URL, headers=self._edgar_headers())
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise DataProviderUnavailableError("sec_edgar", str(exc)) from exc
            except httpx.HTTPError as exc:
                raise DataProviderUnavailableError("sec_edgar", str(exc)) from exc
            data = response.json()

        mapping = {
            entry["ticker"].upper(): str(entry["cik_str"]).zfill(10)
            for entry in data.values()
            if entry.get("ticker")
        }
        _ticker_cik_cache["map"] = mapping
        return mapping

    # ------------------------------------------------------------------
    # Recent filings
    # ------------------------------------------------------------------
    async def get_recent_filings(self, ticker: str, form_type: str = "10-K", limit: int = 5) -> SecFilingsResponse:
        ticker = ticker.strip().upper()
        cache_key = f"{ticker}:{form_type}:{limit}"
        if cache_key in _filings_cache:
            return _filings_cache[cache_key]

        last_error: Optional[Exception] = None
        if self.settings.sec_api_key:
            try:
                filings = await self._get_filings_sec_api(ticker, form_type, limit)
                response = SecFilingsResponse(
                    ticker=ticker, provider_used="sec-api.io", filings=filings, fetched_at=datetime.now(timezone.utc)
                )
                _filings_cache[cache_key] = response
                return response
            except Exception as exc:  # noqa: BLE001
                logger.warning("sec-api.io failed for %s, falling back to EDGAR: %s", ticker, exc)
                last_error = exc

        try:
            filings = await self._get_filings_edgar(ticker, form_type, limit)
            response = SecFilingsResponse(
                ticker=ticker, provider_used="sec_edgar", filings=filings, fetched_at=datetime.now(timezone.utc)
            )
            _filings_cache[cache_key] = response
            return response
        except NoDataFoundError:
            raise
        except Exception as exc:  # noqa: BLE001
            last_error = exc

        raise AllProvidersFailedError("דיווחי SEC", detail=str(last_error) if last_error else "")

    async def _get_filings_sec_api(self, ticker: str, form_type: str, limit: int) -> list[SecFiling]:
        return await asyncio.to_thread(self._fetch_sec_api_sync, ticker, form_type, limit)

    def _fetch_sec_api_sync(self, ticker: str, form_type: str, limit: int) -> list[SecFiling]:
        try:
            from sec_api import QueryApi
        except ImportError as exc:  # pragma: no cover - dependency always declared, defensive only
            raise DataProviderUnavailableError("sec-api.io", "sec-api package not installed") from exc

        query_api = QueryApi(api_key=self.settings.sec_api_key)
        query = {
            "query": f'ticker:{ticker} AND formType:"{form_type}"',
            "from": "0",
            "size": str(limit),
            "sort": [{"filedAt": {"order": "desc"}}],
        }
        try:
            result = query_api.get_filings(query)
        except Exception as exc:  # noqa: BLE001
            message = str(exc)
            if "429" in message:
                raise DataProviderRateLimitError("sec-api.io") from exc
            raise DataProviderUnavailableError("sec-api.io", message) from exc

        filings = []
        for item in result.get("filings", []):
            filed_at = None
            if item.get("filedAt"):
                try:
                    filed_at = datetime.fromisoformat(item["filedAt"].replace("Z", "+00:00"))
                except ValueError:
                    filed_at = None
            filings.append(
                SecFiling(
                    provider="sec-api.io",
                    ticker=ticker,
                    cik=str(item.get("cik", "")),
                    company_name=item.get("companyName", ""),
                    form_type=form_type if form_type in ("10-K", "10-Q", "8-K") else "OTHER",
                    filed_at=filed_at,
                    filing_url=item.get("linkToFilingDetails", item.get("linkToHtml", "")),
                    accession_no=item.get("accessionNo", ""),
                )
            )
        return filings

    @external_api_retry()
    async def _get_filings_edgar(self, ticker: str, form_type: str, limit: int) -> list[SecFiling]:
        cik10 = await self.resolve_cik(ticker)
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                EDGAR_SUBMISSIONS_URL.format(cik10=cik10), headers=self._edgar_headers()
            )
            if response.status_code == 429:
                raise DataProviderRateLimitError("sec_edgar")
            if response.status_code == 404:
                raise NoDataFoundError(ticker)
            response.raise_for_status()
            data = response.json()

        recent = data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        accession_numbers = recent.get("accessionNumber", [])
        primary_docs = recent.get("primaryDocument", [])
        company_name = data.get("name", "")

        filings: list[SecFiling] = []
        for i, form in enumerate(forms):
            if form != form_type:
                continue
            accession_no = accession_numbers[i]
            accession_no_nodash = accession_no.replace("-", "")
            filing_url = (
                f"https://www.sec.gov/Archives/edgar/data/{int(cik10)}/"
                f"{accession_no_nodash}/{primary_docs[i]}"
            )
            filed_at = None
            try:
                filed_at = datetime.strptime(dates[i], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except (ValueError, IndexError):
                pass
            filings.append(
                SecFiling(
                    provider="sec_edgar",
                    ticker=ticker,
                    cik=cik10,
                    company_name=company_name,
                    form_type=form_type if form_type in ("10-K", "10-Q", "8-K") else "OTHER",
                    filed_at=filed_at,
                    filing_url=filing_url,
                    accession_no=accession_no,
                )
            )
            if len(filings) >= limit:
                break

        if not filings:
            raise NoDataFoundError(f"{ticker} ({form_type})")
        return filings

    # ------------------------------------------------------------------
    # XBRL company facts -> key financial-health metrics
    # ------------------------------------------------------------------
    @external_api_retry()
    async def get_company_facts(self, ticker: str) -> CompanyFinancialFacts:
        ticker = ticker.strip().upper()
        if ticker in _facts_cache:
            return _facts_cache[ticker]

        cik10 = await self.resolve_cik(ticker)
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                EDGAR_COMPANY_FACTS_URL.format(cik10=cik10), headers=self._edgar_headers()
            )
            if response.status_code == 429:
                raise DataProviderRateLimitError("sec_edgar")
            if response.status_code == 404:
                raise NoDataFoundError(ticker)
            response.raise_for_status()
            data = response.json()

        us_gaap = data.get("facts", {}).get("us-gaap", {})
        facts = CompanyFinancialFacts(ticker=ticker, cik=cik10, company_name=data.get("entityName", ""))

        for field_name, tag_candidates in _XBRL_TAG_CANDIDATES.items():
            value, fy, fp = self._extract_latest_annual_value(us_gaap, tag_candidates)
            if value is not None:
                setattr(facts, field_name, value)
                facts.fiscal_year = facts.fiscal_year or fy
                facts.fiscal_period = facts.fiscal_period or fp

        _facts_cache[ticker] = facts
        return facts

    @staticmethod
    def _extract_latest_annual_value(
        us_gaap: dict[str, Any], tag_candidates: list[str]
    ) -> tuple[Optional[float], Optional[int], Optional[str]]:
        for tag in tag_candidates:
            tag_data = us_gaap.get(tag)
            if not tag_data:
                continue
            usd_units = tag_data.get("units", {}).get("USD") or tag_data.get("units", {}).get("USD/shares")
            if not usd_units:
                continue
            annual_entries = [entry for entry in usd_units if entry.get("form") == "10-K" and entry.get("fy")]
            if not annual_entries:
                continue
            latest = max(annual_entries, key=lambda e: (e.get("fy", 0), e.get("end", "")))
            return latest.get("val"), latest.get("fy"), latest.get("fp")
        return None, None, None


sec_service = SecService()
