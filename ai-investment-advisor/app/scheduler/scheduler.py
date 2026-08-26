"""
In-process background job scheduler (AsyncIOScheduler from APScheduler).

Chosen over Celery+Redis: this app runs as a single FastAPI process, and
AsyncIOScheduler schedules coroutine jobs directly on FastAPI's own asyncio
event loop - no broker, no separate worker process, no extra infrastructure
to deploy for two lightweight periodic jobs. If this ever needs multiple
worker processes/machines sharing a job queue, Celery+Redis (already an
optional part of the original tech-stack spec) would be the right upgrade.

Started/stopped from app/main.py's lifespan. Job definitions are
re-registered on every process start (the default in-memory job store),
which is intentional for a single-process deployment; on a fresh database
(no section has ever been saved), each job is also given an immediate
first run so the dashboard isn't empty while waiting for the first
interval/cron tick.
"""
from __future__ import annotations

from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import get_settings
from app.core.logging import get_logger
from app.scheduler import store
from app.scheduler.jobs import (
    JOB_DAILY_SCAN,
    JOB_NAMES_HE,
    JOB_NEWS_POLLING,
    daily_report_scan_job,
    news_polling_job,
)

logger = get_logger(__name__)

_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone="UTC")
    return _scheduler


async def start_scheduler() -> None:
    settings = get_settings()
    scheduler = get_scheduler()
    if scheduler.running:
        return

    now = datetime.now(timezone.utc)
    # Bootstrap: if a section has never been populated, run its job once
    # immediately instead of waiting for the first scheduled tick. Passing
    # next_run_time=None to add_job means "add as paused", NOT "use the
    # trigger's normal schedule" - so that kwarg must only be included at
    # all when we actually want an immediate run; otherwise it's omitted
    # entirely and APScheduler computes it from the trigger as usual.
    news_job_kwargs: dict = dict(
        trigger=IntervalTrigger(minutes=settings.news_polling_interval_minutes),
        id=JOB_NEWS_POLLING,
        name=JOB_NAMES_HE[JOB_NEWS_POLLING],
        max_instances=1,
        coalesce=True,
        misfire_grace_time=120,
        replace_existing=True,
    )
    if not await store.has_section(store.SECTION_NEWS):
        news_job_kwargs["next_run_time"] = now

    daily_job_kwargs: dict = dict(
        trigger=CronTrigger(hour=settings.daily_scan_hour_utc, minute=settings.daily_scan_minute_utc, timezone="UTC"),
        id=JOB_DAILY_SCAN,
        name=JOB_NAMES_HE[JOB_DAILY_SCAN],
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
        replace_existing=True,
    )
    if not await store.has_section(store.SECTION_RISK):
        daily_job_kwargs["next_run_time"] = now

    scheduler.add_job(news_polling_job, **news_job_kwargs)
    scheduler.add_job(daily_report_scan_job, **daily_job_kwargs)

    scheduler.start()
    logger.info(
        "[SCHEDULER] started: news polling every %sm, daily SEC scan at %02d:%02d UTC",
        settings.news_polling_interval_minutes,
        settings.daily_scan_hour_utc,
        settings.daily_scan_minute_utc,
    )


async def shutdown_scheduler() -> None:
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("[SCHEDULER] stopped")
