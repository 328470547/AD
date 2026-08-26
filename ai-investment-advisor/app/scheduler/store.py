"""
Persistence for the background scheduler:
  * last-known-good dashboard sections (survive across job runs; a failed
    run leaves the previous good result in place rather than blanking it)
  * job run history, for monitoring background job health
  * seen-filing tracking, so the daily scan can report genuinely *new*
    10-K/10-Q filings instead of silently re-fetching the same ones

This is the layer that makes "the dashboard reads pre-computed data instead
of triggering live API/LLM calls" actually true: app/scheduler/jobs.py
writes here, and app/api/routes/analysis.py's default snapshot read comes
from here instead of app/agents/orchestrator.py's live compute path.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel
from sqlalchemy import select

from app.agents.schemas import (
    CompanyReportAnalysis,
    DashboardSnapshot,
    NewsSentimentAnalysis,
    RiskAssessment,
    SmallCapOpportunity,
)
from app.core.config import get_settings
from app.core.database import AgentSnapshotSection, AsyncSessionLocal, JobRunLog, SeenFiling
from app.core.logging import get_logger
from app.models.schemas import SecFiling
from app.scheduler.schemas import JobRunSummary, SectionStatus

logger = get_logger(__name__)

SECTION_NEWS = "news_sentiment"
SECTION_RISK = "risk_alerts"
SECTION_REPORTS = "company_reports"
SECTION_SMALLCAP = "smallcap_opportunities"

# Whether each section stores a single object or a list of them, and which
# Pydantic model to parse the stored JSON back into.
_SECTION_MODELS: dict[str, tuple[type[BaseModel], bool]] = {
    SECTION_NEWS: (NewsSentimentAnalysis, False),
    SECTION_RISK: (RiskAssessment, True),
    SECTION_REPORTS: (CompanyReportAnalysis, True),
    SECTION_SMALLCAP: (SmallCapOpportunity, True),
}


def _dump(payload: BaseModel | list[BaseModel]) -> str:
    if isinstance(payload, list):
        data = [item.model_dump(mode="json") for item in payload]
    else:
        data = payload.model_dump(mode="json")
    return json.dumps(data, ensure_ascii=False)


async def save_section(section: str, payload: BaseModel | list[BaseModel]) -> None:
    """Upsert the last-known-good payload for one dashboard section. Call
    this only on a successful job run - see module docstring."""
    payload_json = _dump(payload)
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as session:
        async with session.begin():
            result = await session.execute(
                select(AgentSnapshotSection).where(AgentSnapshotSection.section == section)
            )
            row = result.scalar_one_or_none()
            if row is None:
                session.add(AgentSnapshotSection(section=section, payload_json=payload_json, updated_at=now))
            else:
                row.payload_json = payload_json
                row.updated_at = now


async def has_section(section: str) -> bool:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AgentSnapshotSection.id).where(AgentSnapshotSection.section == section)
        )
        return result.scalar_one_or_none() is not None


async def load_latest() -> Optional[DashboardSnapshot]:
    """Assemble a DashboardSnapshot from whatever sections have been saved
    so far. Returns None if no background job has ever completed (e.g. a
    fresh install before the first job run) so the caller can fall back to
    a live compute for that one request."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AgentSnapshotSection))
        rows = {row.section: row for row in result.scalars().all()}

    if not rows:
        return None

    settings = get_settings()
    snapshot = DashboardSnapshot(
        generated_at=datetime.now(timezone.utc),
        watchlist=list(settings.watchlist_tickers),
        source="cache",
    )

    for section, (model, is_list) in _SECTION_MODELS.items():
        row = rows.get(section)
        if row is None:
            continue
        data = json.loads(row.payload_json)
        value = [model.model_validate(item) for item in data] if is_list else model.model_validate(data)
        if section == SECTION_NEWS:
            snapshot.news_sentiment, snapshot.news_updated_at = value, row.updated_at
        elif section == SECTION_RISK:
            snapshot.risk_alerts, snapshot.risk_alerts_updated_at = value, row.updated_at
        elif section == SECTION_REPORTS:
            snapshot.company_reports, snapshot.company_reports_updated_at = value, row.updated_at
        elif section == SECTION_SMALLCAP:
            snapshot.smallcap_opportunities, snapshot.smallcap_updated_at = value, row.updated_at

    return snapshot


async def section_statuses() -> list[SectionStatus]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AgentSnapshotSection))
        rows = {row.section: row for row in result.scalars().all()}
    return [
        SectionStatus(section=section, has_data=section in rows, updated_at=rows[section].updated_at if section in rows else None)
        for section in _SECTION_MODELS
    ]


async def record_job_run(
    job_name: str, started_at: datetime, finished_at: datetime, status: str, summary_he: str, error: str = ""
) -> None:
    async with AsyncSessionLocal() as session:
        async with session.begin():
            session.add(
                JobRunLog(
                    job_name=job_name,
                    started_at=started_at,
                    finished_at=finished_at,
                    status=status,
                    summary_he=summary_he,
                    error=error,
                )
            )


async def recent_job_runs(job_name: Optional[str] = None, limit: int = 20) -> list[JobRunSummary]:
    async with AsyncSessionLocal() as session:
        # Secondary sort by id: two runs can share the same started_at
        # timestamp (datetime.now() resolution / fast successive runs), and
        # without a tiebreaker the DB's ordering among ties is unspecified.
        stmt = select(JobRunLog).order_by(JobRunLog.started_at.desc(), JobRunLog.id.desc()).limit(limit)
        if job_name:
            stmt = stmt.where(JobRunLog.job_name == job_name)
        result = await session.execute(stmt)
        rows = result.scalars().all()
    return [
        JobRunSummary(
            job_name=row.job_name,
            started_at=row.started_at,
            finished_at=row.finished_at,
            duration_seconds=(row.finished_at - row.started_at).total_seconds(),
            status=row.status,
            summary_he=row.summary_he,
            error=row.error,
        )
        for row in rows
    ]


async def mark_seen_and_count_new(ticker: str, filings: list[SecFiling]) -> int:
    """Persist filings not previously seen for this ticker; returns how
    many were new. Logs each new filing individually (not just the job's
    aggregate summary) so it's visible in the monitoring logs as it
    happens."""
    if not filings:
        return 0

    new_count = 0
    async with AsyncSessionLocal() as session:
        async with session.begin():
            for filing in filings:
                if not filing.accession_no:
                    continue
                result = await session.execute(
                    select(SeenFiling.id).where(SeenFiling.accession_no == filing.accession_no)
                )
                if result.scalar_one_or_none() is not None:
                    continue
                session.add(
                    SeenFiling(
                        ticker=ticker,
                        accession_no=filing.accession_no,
                        form_type=filing.form_type,
                        filed_at=filing.filed_at,
                    )
                )
                new_count += 1
                logger.info(
                    "[NEW FILING] %s: %s filed %s - %s",
                    ticker,
                    filing.form_type,
                    filing.filed_at.date() if filing.filed_at else "unknown date",
                    filing.filing_url,
                )
    return new_count
