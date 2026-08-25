"""
Combines the Phase 2 data services with the Phase 3 agents into a single
DashboardSnapshot - the one call the Streamlit dashboard (Phase 4) needs to
render every zone. Each of the four sections (risk alerts, news sentiment,
company reports, small-cap screener) is fetched independently and degrades
gracefully: a failure in one never blocks the others, it just attaches a
Hebrew error message to that section.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional

from app.agents.news_sentiment_agent import news_sentiment_agent
from app.agents.report_analyzer_agent import report_analyzer_agent
from app.agents.risk_assessor_agent import risk_assessor_agent
from app.agents.schemas import (
    CompanyReportAnalysis,
    DashboardSnapshot,
    NewsSentimentAnalysis,
    RiskAssessment,
    SmallCapOpportunity,
)
from app.agents.smallcap_screener_agent import ScreenerCandidate, smallcap_screener_agent
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.schemas import CompanyFinancialFacts, StockQuote
from app.services.news_service import news_service
from app.services.sec_service import sec_service
from app.services.stock_service import stock_service
from app.utils.errors import AdvisorError

logger = get_logger(__name__)

# Bounds on how many tickers get an LLM-backed deep-dive per snapshot, to
# keep latency/cost sane for a dashboard auto-refresh.
MAX_RISK_ASSESSMENTS = 8
MAX_COMPANY_REPORTS = 5


def _error_he(exc: BaseException) -> str:
    if isinstance(exc, AdvisorError):
        return exc.message_he
    return "אירעה שגיאה בלתי צפויה בעת יצירת הניתוח."


async def _fetch_quotes(tickers: list[str]) -> dict[str, StockQuote]:
    results = await asyncio.gather(*(stock_service.get_quote(t) for t in tickers), return_exceptions=True)
    quotes: dict[str, StockQuote] = {}
    for ticker, result in zip(tickers, results):
        if isinstance(result, Exception):
            logger.info("dashboard: quote fetch failed for %s: %s", ticker, result)
        else:
            quotes[ticker] = result
    return quotes


async def _fetch_facts(tickers: list[str]) -> dict[str, CompanyFinancialFacts]:
    results = await asyncio.gather(*(sec_service.get_company_facts(t) for t in tickers), return_exceptions=True)
    facts: dict[str, CompanyFinancialFacts] = {}
    for ticker, result in zip(tickers, results):
        if isinstance(result, Exception):
            logger.info("dashboard: facts fetch failed for %s: %s", ticker, result)
        else:
            facts[ticker] = result
    return facts


async def _build_risk_alerts(
    tickers: list[str], quotes: dict[str, StockQuote], facts: dict[str, CompanyFinancialFacts]
) -> list[RiskAssessment]:
    subset = tickers[:MAX_RISK_ASSESSMENTS]
    results = await asyncio.gather(
        *(risk_assessor_agent.assess(t, quote=quotes.get(t), facts=facts.get(t)) for t in subset),
        return_exceptions=True,
    )
    assessments: list[RiskAssessment] = []
    last_error: Optional[Exception] = None
    for ticker, result in zip(subset, results):
        if isinstance(result, Exception):
            logger.info("dashboard: risk assessment failed for %s: %s", ticker, result)
            last_error = result
        else:
            assessments.append(result)

    # If every single assessment failed (e.g. Claude is misconfigured), that
    # is an error state - showing an empty "no risk detected" list would be
    # actively misleading for a risk-alerts feature, so surface it as a
    # section error instead of silently returning [].
    if subset and not assessments:
        raise AdvisorError(
            f"All risk assessments failed: {last_error}",
            "לא ניתן היה להפיק הערכות סיכון עבור אף אחד מהניירות ברשימת המעקב.",
            status_code=502,
        )

    # Surface the flagged/high-risk names first for the alerts zone.
    return sorted(assessments, key=lambda a: (not a.is_flagged, a.risk_level != "גבוה"))


async def _build_news_sentiment() -> NewsSentimentAnalysis:
    news = await news_service.get_financial_news()
    return await news_sentiment_agent.analyze(news.articles)


async def _build_company_reports(
    tickers: list[str], facts: dict[str, CompanyFinancialFacts]
) -> list[CompanyReportAnalysis]:
    subset = [t for t in tickers if t in facts][:MAX_COMPANY_REPORTS]
    if not subset:
        raise AdvisorError(
            "No fundamentals available for any watchlist ticker",
            "לא נמצאו נתונים פיננסיים עבור אף אחד מהניירות ברשימת המעקב.",
            status_code=404,
        )

    async def _one(ticker: str) -> CompanyReportAnalysis:
        filings_response = await sec_service.get_recent_filings(ticker, form_type="10-K", limit=3)
        return await report_analyzer_agent.analyze(ticker, facts.get(ticker), filings_response.filings)

    results = await asyncio.gather(*(_one(t) for t in subset), return_exceptions=True)
    reports: list[CompanyReportAnalysis] = []
    for ticker, result in zip(subset, results):
        if isinstance(result, Exception):
            logger.info("dashboard: report analysis failed for %s: %s", ticker, result)
        else:
            reports.append(result)
    if not reports:
        raise AdvisorError("All company report analyses failed", "ניתוח הדוחות הכספיים נכשל עבור כל הניירות.", status_code=502)
    return reports


async def _build_smallcap_opportunities(
    tickers: list[str], quotes: dict[str, StockQuote], facts: dict[str, CompanyFinancialFacts], threshold: float
) -> list[SmallCapOpportunity]:
    candidates = [
        ScreenerCandidate(ticker=t, quote=quotes.get(t), facts=facts.get(t), company_name=(facts.get(t).company_name if facts.get(t) else ""))
        for t in tickers
        if t in quotes
    ]
    return await smallcap_screener_agent.screen(candidates, market_cap_threshold_usd=threshold)


async def build_dashboard_snapshot(watchlist: Optional[list[str]] = None) -> DashboardSnapshot:
    settings = get_settings()
    tickers = [t.strip().upper() for t in (watchlist or settings.watchlist_tickers)]

    quotes, facts = await asyncio.gather(_fetch_quotes(tickers), _fetch_facts(tickers))

    snapshot = DashboardSnapshot(generated_at=datetime.now(timezone.utc), watchlist=tickers)

    section_results = await asyncio.gather(
        _build_risk_alerts(tickers, quotes, facts),
        _build_news_sentiment(),
        _build_company_reports(tickers, facts),
        _build_smallcap_opportunities(tickers, quotes, facts, settings.smallcap_market_cap_usd),
        return_exceptions=True,
    )
    risk_result, news_result, reports_result, smallcap_result = section_results

    if isinstance(risk_result, Exception):
        snapshot.risk_alerts_error_he = _error_he(risk_result)
        logger.warning("dashboard risk alerts section failed: %s", risk_result)
    else:
        snapshot.risk_alerts = risk_result

    if isinstance(news_result, Exception):
        snapshot.news_error_he = _error_he(news_result)
        logger.warning("dashboard news sentiment section failed: %s", news_result)
    else:
        snapshot.news_sentiment = news_result

    if isinstance(reports_result, Exception):
        snapshot.company_reports_error_he = _error_he(reports_result)
        logger.warning("dashboard company reports section failed: %s", reports_result)
    else:
        snapshot.company_reports = reports_result

    if isinstance(smallcap_result, Exception):
        snapshot.smallcap_error_he = _error_he(smallcap_result)
        logger.warning("dashboard smallcap section failed: %s", smallcap_result)
    else:
        snapshot.smallcap_opportunities = smallcap_result

    return snapshot
