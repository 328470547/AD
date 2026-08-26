from unittest.mock import AsyncMock, patch

import pytest

from app.agents.schemas import NewsSentimentAnalysis
from app.core.database import AgentSnapshotSection, AsyncSessionLocal, JobRunLog, SeenFiling, init_db
from app.scheduler import jobs, store
from app.utils.errors import DataProviderConfigError

SAMPLE_NEWS = NewsSentimentAnalysis(
    market_sentiment="חיובי",
    headline_he="השוק עולה",
    market_impact_summary_he="סיכום.",
    reasoning_he="שרשרת חשיבה.",
)


@pytest.fixture(autouse=True)
async def _clean_db():
    await init_db()
    async with AsyncSessionLocal() as session:
        async with session.begin():
            for model in (AgentSnapshotSection, JobRunLog, SeenFiling):
                await session.execute(model.__table__.delete())
    yield


@pytest.mark.asyncio
async def test_news_polling_job_success_saves_section_and_logs_run():
    with patch("app.scheduler.jobs.build_news_sentiment", new=AsyncMock(return_value=SAMPLE_NEWS)):
        await jobs.news_polling_job()

    snapshot = await store.load_latest()
    assert snapshot is not None
    assert snapshot.news_sentiment.headline_he == "השוק עולה"

    runs = await store.recent_job_runs(job_name=jobs.JOB_NEWS_POLLING)
    assert len(runs) == 1
    assert runs[0].status == "success"
    assert "השוק עולה" in runs[0].summary_he


@pytest.mark.asyncio
async def test_news_polling_job_failure_logs_run_without_saving_section():
    with patch(
        "app.scheduler.jobs.build_news_sentiment",
        new=AsyncMock(side_effect=DataProviderConfigError("anthropic")),
    ):
        await jobs.news_polling_job()

    assert await store.load_latest() is None
    runs = await store.recent_job_runs(job_name=jobs.JOB_NEWS_POLLING)
    assert len(runs) == 1
    assert runs[0].status == "failure"
    assert runs[0].summary_he  # Hebrew message present


@pytest.mark.asyncio
async def test_news_polling_job_does_not_wipe_previous_good_data_on_later_failure():
    """A stale-but-valid result should keep serving while the scheduler
    retries, rather than the dashboard going blank on one bad tick."""
    with patch("app.scheduler.jobs.build_news_sentiment", new=AsyncMock(return_value=SAMPLE_NEWS)):
        await jobs.news_polling_job()

    with patch(
        "app.scheduler.jobs.build_news_sentiment",
        new=AsyncMock(side_effect=DataProviderConfigError("anthropic")),
    ):
        await jobs.news_polling_job()

    snapshot = await store.load_latest()
    assert snapshot.news_sentiment.headline_he == "השוק עולה"  # still there

    runs = await store.recent_job_runs(job_name=jobs.JOB_NEWS_POLLING)
    assert len(runs) == 2
    assert {r.status for r in runs} == {"success", "failure"}


@pytest.mark.asyncio
async def test_daily_report_scan_job_partial_failure_still_records_success():
    """If some sections succeed and others fail, the job as a whole is a
    (partial) success - only a total wipeout should count as a failure."""
    with patch("app.scheduler.jobs.fetch_quotes", new=AsyncMock(return_value={})), patch(
        "app.scheduler.jobs.fetch_facts", new=AsyncMock(return_value={})
    ), patch("app.scheduler.jobs._scan_new_filings", new=AsyncMock(return_value=0)), patch(
        "app.scheduler.jobs.build_risk_alerts", new=AsyncMock(side_effect=RuntimeError("boom"))
    ), patch(
        "app.scheduler.jobs.build_company_reports", new=AsyncMock(side_effect=RuntimeError("boom"))
    ), patch(
        "app.scheduler.jobs.build_smallcap_opportunities", new=AsyncMock(return_value=[])
    ):
        await jobs.daily_report_scan_job()

    runs = await store.recent_job_runs(job_name=jobs.JOB_DAILY_SCAN)
    assert len(runs) == 1
    assert runs[0].status == "success"

    snapshot = await store.load_latest()
    assert snapshot.smallcap_opportunities == []
    assert snapshot.risk_alerts == []  # never saved - that section failed


@pytest.mark.asyncio
async def test_daily_report_scan_job_total_failure_records_failure():
    with patch("app.scheduler.jobs.fetch_quotes", new=AsyncMock(return_value={})), patch(
        "app.scheduler.jobs.fetch_facts", new=AsyncMock(return_value={})
    ), patch("app.scheduler.jobs._scan_new_filings", new=AsyncMock(return_value=0)), patch(
        "app.scheduler.jobs.build_risk_alerts", new=AsyncMock(side_effect=RuntimeError("boom"))
    ), patch(
        "app.scheduler.jobs.build_company_reports", new=AsyncMock(side_effect=RuntimeError("boom"))
    ), patch(
        "app.scheduler.jobs.build_smallcap_opportunities", new=AsyncMock(side_effect=RuntimeError("boom"))
    ):
        await jobs.daily_report_scan_job()

    runs = await store.recent_job_runs(job_name=jobs.JOB_DAILY_SCAN)
    assert len(runs) == 1
    assert runs[0].status == "failure"
