import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.core.database import AgentSnapshotSection, AsyncSessionLocal, JobRunLog, SeenFiling, init_db
from app.scheduler import scheduler as scheduler_module
from app.scheduler.jobs import JOB_DAILY_SCAN, JOB_NEWS_POLLING


@pytest.fixture(autouse=True)
async def _reset_scheduler():
    scheduler_module._scheduler = None
    await init_db()
    async with AsyncSessionLocal() as session:
        async with session.begin():
            for model in (AgentSnapshotSection, JobRunLog, SeenFiling):
                await session.execute(model.__table__.delete())
    yield
    sched = scheduler_module.get_scheduler()
    if sched.running:
        sched.shutdown(wait=False)
    scheduler_module._scheduler = None


@pytest.mark.asyncio
async def test_jobs_get_a_real_next_run_time_not_paused():
    """Regression test: APScheduler's add_job(next_run_time=None) means
    'add the job as paused', not 'use the trigger's own schedule'. A naive
    bootstrap-on-fresh-db implementation could accidentally pass None for
    every job that isn't being bootstrapped, permanently pausing it. Both
    jobs must always end up with a real next_run_time."""
    with patch("app.scheduler.scheduler.news_polling_job", new=AsyncMock(return_value=None)), patch(
        "app.scheduler.scheduler.daily_report_scan_job", new=AsyncMock(return_value=None)
    ):
        await scheduler_module.start_scheduler()
        await asyncio.sleep(0.05)  # let the immediate bootstrap runs finish cleanly

        sched = scheduler_module.get_scheduler()
        jobs_by_id = {job.id: job for job in sched.get_jobs()}
        assert jobs_by_id[JOB_NEWS_POLLING].next_run_time is not None
        assert jobs_by_id[JOB_DAILY_SCAN].next_run_time is not None


@pytest.mark.asyncio
async def test_start_scheduler_is_idempotent():
    with patch("app.scheduler.scheduler.news_polling_job", new=AsyncMock(return_value=None)), patch(
        "app.scheduler.scheduler.daily_report_scan_job", new=AsyncMock(return_value=None)
    ):
        await scheduler_module.start_scheduler()
        await asyncio.sleep(0.05)
        await scheduler_module.start_scheduler()  # must not raise / double-add

        sched = scheduler_module.get_scheduler()
        assert len(sched.get_jobs()) == 2
