from __future__ import annotations

from fastapi import APIRouter, Query

from app.agents.news_sentiment_agent import news_sentiment_agent
from app.agents.orchestrator import build_dashboard_snapshot
from app.agents.report_analyzer_agent import report_analyzer_agent
from app.agents.risk_assessor_agent import risk_assessor_agent
from app.agents.schemas import CompanyReportAnalysis, DashboardSnapshot, NewsSentimentAnalysis, RiskAssessment
from app.scheduler import store as snapshot_store
from app.services.news_service import news_service
from app.services.sec_service import sec_service
from app.services.stock_service import stock_service

router = APIRouter(prefix="/api", tags=["analysis"])


@router.get("/dashboard/snapshot", response_model=DashboardSnapshot)
async def get_dashboard_snapshot(
    tickers: str | None = Query(
        None, description="Comma-separated ticker override; triggers a live compute instead of the cached snapshot"
    ),
) -> DashboardSnapshot:
    """The one call the Streamlit dashboard needs: risk alerts, news
    sentiment, company report analyses and small-cap opportunities.

    By default this reads the background scheduler's last saved results
    (fast, no live API/LLM calls in the request path - see
    app/scheduler/jobs.py). Passing an explicit `tickers` override falls
    back to a live compute for that one request, since the scheduler only
    maintains data for the server's configured watchlist. If no job has
    completed yet (fresh install), it also falls back to a live compute so
    the dashboard isn't empty while waiting for the first scheduled run.
    """
    if tickers:
        watchlist = [t.strip().upper() for t in tickers.split(",") if t.strip()]
        return await build_dashboard_snapshot(watchlist)

    cached = await snapshot_store.load_latest()
    if cached is not None:
        return cached
    return await build_dashboard_snapshot()


@router.get("/analysis/news-sentiment", response_model=NewsSentimentAnalysis)
async def get_news_sentiment(
    query: str = Query("stock market OR earnings OR federal reserve"),
) -> NewsSentimentAnalysis:
    news = await news_service.get_financial_news(query=query)
    return await news_sentiment_agent.analyze(news.articles)


@router.get("/analysis/risk/{ticker}", response_model=RiskAssessment)
async def get_risk_assessment(ticker: str) -> RiskAssessment:
    quote = None
    facts = None
    try:
        quote = await stock_service.get_quote(ticker)
    except Exception:  # noqa: BLE001 - risk assessment can proceed with partial data
        pass
    try:
        facts = await sec_service.get_company_facts(ticker)
    except Exception:  # noqa: BLE001
        pass
    return await risk_assessor_agent.assess(ticker, quote=quote, facts=facts)


@router.get("/analysis/report/{ticker}", response_model=CompanyReportAnalysis)
async def get_report_analysis(ticker: str) -> CompanyReportAnalysis:
    facts = await sec_service.get_company_facts(ticker)
    filings_response = await sec_service.get_recent_filings(ticker, form_type="10-K", limit=3)
    return await report_analyzer_agent.analyze(ticker, facts, filings_response.filings)
