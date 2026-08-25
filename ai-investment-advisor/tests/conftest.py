"""
Test-session-wide setup, executed by pytest before any test module (and
therefore before any `app.*` import) is collected.

Two things must be set via environment variables here, before `app.core.config
.get_settings()` is ever called (it's `@lru_cache`d, so whatever it reads
first wins for the whole test session):

  * DATABASE_URL - point at an isolated temp-file SQLite DB instead of the
    dev DB at ./data/app.db. The scheduler/store tests actually read and
    write rows now (unlike the Phase 1-2 services, which only ever used
    in-memory TTLCache), so sharing the dev DB across test runs would leak
    state between runs and pollute real dev data.
  * SCHEDULER_ENABLED=false - tests must never spin up the real background
    scheduler (which would fire live API/LLM calls on a timer during the
    test session); scheduler behavior is tested directly and explicitly
    instead (see test_scheduler_*.py).
"""
import os
import tempfile

_tmp_dir = tempfile.mkdtemp(prefix="ai-advisor-test-")
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{_tmp_dir}/test.db")
os.environ.setdefault("SCHEDULER_ENABLED", "false")
os.environ.setdefault("SEC_EDGAR_USER_AGENT", "AI Investment Advisor Tests test@example.com")
