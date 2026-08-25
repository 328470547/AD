import pytest
import respx
from httpx import Response

from app.services.sec_service import (
    EDGAR_COMPANY_FACTS_URL,
    EDGAR_SUBMISSIONS_URL,
    EDGAR_TICKER_MAP_URL,
    SecService,
)
from app.utils.errors import NoDataFoundError

CIK10 = "0000320193"


@pytest.fixture(autouse=True)
def _clear_caches():
    from app.services import sec_service as mod

    mod._ticker_cik_cache.clear()
    mod._filings_cache.clear()
    mod._facts_cache.clear()
    yield


@pytest.mark.asyncio
@respx.mock
async def test_resolve_cik():
    respx.get(EDGAR_TICKER_MAP_URL).mock(
        return_value=Response(200, json={"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}})
    )
    service = SecService()
    cik = await service.resolve_cik("aapl")
    assert cik == CIK10


@pytest.mark.asyncio
@respx.mock
async def test_get_recent_filings_edgar_fallback():
    respx.get(EDGAR_TICKER_MAP_URL).mock(
        return_value=Response(200, json={"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}})
    )
    respx.get(EDGAR_SUBMISSIONS_URL.format(cik10=CIK10)).mock(
        return_value=Response(
            200,
            json={
                "name": "Apple Inc.",
                "filings": {
                    "recent": {
                        "form": ["10-K", "10-Q", "10-K"],
                        "filingDate": ["2025-11-01", "2025-08-01", "2024-11-01"],
                        "accessionNumber": ["0000320193-25-000001", "0000320193-25-000002", "0000320193-24-000001"],
                        "primaryDocument": ["aapl-10k.htm", "aapl-10q.htm", "aapl-10k-2024.htm"],
                    }
                },
            },
        )
    )
    service = SecService()
    response = await service.get_recent_filings("AAPL", form_type="10-K", limit=5)
    assert response.provider_used == "sec_edgar"
    assert len(response.filings) == 2
    assert response.filings[0].form_type == "10-K"
    assert "aapl-10k.htm" in response.filings[0].filing_url


@pytest.mark.asyncio
@respx.mock
async def test_get_recent_filings_no_match_raises_not_found():
    respx.get(EDGAR_TICKER_MAP_URL).mock(
        return_value=Response(200, json={"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}})
    )
    respx.get(EDGAR_SUBMISSIONS_URL.format(cik10=CIK10)).mock(
        return_value=Response(
            200,
            json={"name": "Apple Inc.", "filings": {"recent": {"form": ["8-K"], "filingDate": ["2025-01-01"], "accessionNumber": ["x"], "primaryDocument": ["x.htm"]}}},
        )
    )
    service = SecService()
    with pytest.raises(NoDataFoundError):
        await service.get_recent_filings("AAPL", form_type="10-K", limit=5)


@pytest.mark.asyncio
@respx.mock
async def test_get_company_facts_extracts_key_metrics():
    respx.get(EDGAR_TICKER_MAP_URL).mock(
        return_value=Response(200, json={"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}})
    )
    respx.get(EDGAR_COMPANY_FACTS_URL.format(cik10=CIK10)).mock(
        return_value=Response(
            200,
            json={
                "entityName": "Apple Inc.",
                "facts": {
                    "us-gaap": {
                        "Revenues": {
                            "units": {
                                "USD": [
                                    {"form": "10-K", "fy": 2025, "fp": "FY", "end": "2025-09-30", "val": 400000000000}
                                ]
                            }
                        },
                        "NetIncomeLoss": {
                            "units": {
                                "USD": [
                                    {"form": "10-K", "fy": 2025, "fp": "FY", "end": "2025-09-30", "val": 100000000000}
                                ]
                            }
                        },
                    }
                },
            },
        )
    )
    service = SecService()
    facts = await service.get_company_facts("AAPL")
    assert facts.revenue_usd == 400000000000
    assert facts.net_income_usd == 100000000000
    assert facts.fiscal_year == 2025
