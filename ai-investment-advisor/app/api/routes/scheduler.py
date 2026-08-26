"""
Monitoring endpoint for the background scheduler: what jobs are registered
and when they next run, per-section data freshness, and recent job run
history (success/failure + Hebrew summary). This is what lets an operator
check on background job health without grepping log files, and is what the
dashboard's system-health panel renders.
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.core.config import get_settings
from app.scheduler import store
from app.scheduler.jobs import JOB_NAMES_HE
from app.scheduler.schemas import JobDefinitionStatus, SchedulerStatus
from app.scheduler.scheduler import get_scheduler

router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])


@router.get("/status", response_model=SchedulerStatus)
async def get_scheduler_status(limit: int = Query(20, ge=1, le=100)) -> SchedulerStatus:
    settings = get_settings()
    scheduler = get_scheduler()

    jobs = [
        JobDefinitionStatus(id=job.id, name_he=JOB_NAMES_HE.get(job.id, job.name), next_run_time=job.next_run_time)
        for job in scheduler.get_jobs()
    ]

    return SchedulerStatus(
        enabled=settings.scheduler_enabled,
        running=scheduler.running,
        jobs=jobs,
        sections=await store.section_statuses(),
        recent_runs=await store.recent_job_runs(limit=limit),
    )
