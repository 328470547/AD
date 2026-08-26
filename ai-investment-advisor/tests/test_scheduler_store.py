from datetime import datetime, timezone

import pytest

from app.agents.schemas import NewsSentimentAnalysis, RiskAssessment
from app.core.database import AgentSnapshotSection, AsyncSessionLocal, JobRunLog, SeenFiling, init_db
from app.models.schemas import SecFiling
from app.scheduler import store

SAMPLE_NEWS = NewsSentimentAnalysis(
    market_sentiment="חיובי",
    headline_he="השוק עולה",
    market_impact_summary_he="סיכום השפעה לדוגמה.",
    reasoning_he="שרשרת חשיבה לדוגמה.",
)

SAMPLE_RISK = [
    RiskAssessment(
        ticker="AAPL",
        risk_level="נמוך",
        is_flagged=False,
        warning_headline_he="אין ממצאים חריגים",
        warning_detail_he="לא זוהו סיכונים מהותיים.",
        reasoning_he="שרשרת חשיבה לדוגמה.",
    )
]


@pytest.fixture(autouse=True)
async def _clean_db():
    await init_db()
    async with AsyncSessionLocal() as session:
        async with session.begin():
            for model in (AgentSnapshotSection, JobRunLog, SeenFiling):
                await session.execute(model.__table__.delete())
    yield


@pytest.mark.asyncio
async def test_load_latest_returns_none_when_nothing_saved():
    assert await store.load_latest() is None


@pytest.mark.asyncio
async def test_save_and_load_section_round_trip():
    await store.save_section(store.SECTION_NEWS, SAMPLE_NEWS)
    await store.save_section(store.SECTION_RISK, SAMPLE_RISK)

    snapshot = await store.load_latest()
    assert snapshot is not None
    assert snapshot.source == "cache"
    assert snapshot.news_sentiment.headline_he == "השוק עולה"
    assert snapshot.news_updated_at is not None
    assert len(snapshot.risk_alerts) == 1
    assert snapshot.risk_alerts[0].ticker == "AAPL"
    # Sections never saved stay empty/None rather than erroring.
    assert snapshot.company_reports == []
    assert snapshot.smallcap_opportunities == []


@pytest.mark.asyncio
async def test_save_section_upserts_not_duplicates():
    await store.save_section(store.SECTION_NEWS, SAMPLE_NEWS)
    updated = SAMPLE_NEWS.model_copy(update={"headline_he": "עדכון חדש"})
    await store.save_section(store.SECTION_NEWS, updated)

    snapshot = await store.load_latest()
    assert snapshot.news_sentiment.headline_he == "עדכון חדש"

    async with AsyncSessionLocal() as session:
        from sqlalchemy import select

        result = await session.execute(select(AgentSnapshotSection))
        rows = result.scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_record_and_query_job_runs():
    started = datetime.now(timezone.utc)
    finished = datetime.now(timezone.utc)
    await store.record_job_run("news_polling", started, finished, "success", "עודכן בהצלחה")
    await store.record_job_run("news_polling", started, finished, "failure", "נכשל", error="boom")

    runs = await store.recent_job_runs(job_name="news_polling", limit=10)
    assert len(runs) == 2
    assert runs[0].status == "failure"  # most recent first (same timestamp, insertion order via id)


@pytest.mark.asyncio
async def test_mark_seen_and_count_new_only_counts_unseen_filings():
    filing = SecFiling(
        provider="sec_edgar",
        ticker="AAPL",
        form_type="10-K",
        filing_url="https://example.com/10k",
        accession_no="0000320193-25-000001",
    )
    new_count = await store.mark_seen_and_count_new("AAPL", [filing])
    assert new_count == 1

    # Same filing again -> not new.
    new_count_again = await store.mark_seen_and_count_new("AAPL", [filing])
    assert new_count_again == 0


@pytest.mark.asyncio
async def test_section_statuses_reflects_saved_sections():
    await store.save_section(store.SECTION_NEWS, SAMPLE_NEWS)
    statuses = {s.section: s for s in await store.section_statuses()}
    assert statuses[store.SECTION_NEWS].has_data is True
    assert statuses[store.SECTION_RISK].has_data is False
