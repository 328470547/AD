"""API-facing schemas for the scheduler status endpoint."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel


class JobDefinitionStatus(BaseModel):
    id: str
    name_he: str
    next_run_time: Optional[datetime] = None


class JobRunSummary(BaseModel):
    job_name: str
    started_at: datetime
    finished_at: datetime
    duration_seconds: float
    status: Literal["success", "failure"]
    summary_he: str
    error: str = ""


class SectionStatus(BaseModel):
    section: str
    has_data: bool
    updated_at: Optional[datetime] = None


class SchedulerStatus(BaseModel):
    enabled: bool
    running: bool
    jobs: list[JobDefinitionStatus]
    sections: list[SectionStatus]
    recent_runs: list[JobRunSummary]
