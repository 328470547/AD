"""
Background jobs run by the APScheduler instance (app/scheduler/scheduler.py):

  * news_polling_job    - every 15-30 min: fetch breaking financial news and
                           refresh the Hebrew market-sentiment analysis.
  * daily_report_scan_job - once a day: scan the watchlist's SEC filings for
                           genuinely new 10-K/10-Q filings, then refresh
                           risk alerts, company report analyses, and the
                           small-cap screener (all fundamentals-driven, so a
                           daily cadence matches how often the underlying
                           data actually changes).

Every job execution is wrapped by `_run_job`, which provides the "robust,
timestamped logging for every job execution, success, or API failure"
requirement: a start/success/failure log line via the app's normal UTF-8
logger (app/core/logging.py already timestamps every line), plus a durable
JobRunLog row so job health can be inspected via GET /api/scheduler/status
and the dashboard without grepping log files.

A job never lets one failing section abort the others - each dashboard
section is fetched/persisted independently, matching the same
degrade-gracefully philosophy as app/agents/orchestrator.py's live path.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Awaitable, Callable

from app.agents.orchestrator import (
    build_company_reports,
    build_news_sentiment,
    build_risk_alerts,
    build_smallcap_opportunities,
    error_he,
    fetch_facts,
    fetch_quotes,
)
from app.core.config import get_settings
from app.core.logging import get_logger
from app.scheduler import store
from app.services.sec_service import sec_service
from app.utils.errors import AdvisorError

logger = get_logger(__name__)

JOB_NEWS_POLLING = "news_polling"
JOB_DAILY_SCAN = "daily_report_scan"

JOB_NAMES_HE = {
    JOB_NEWS_POLLING: "סריקת חדשות ועדכון סנטימנט",
    JOB_DAILY_SCAN: "סריקת דוחות SEC יומית",
}


async def _run_job(job_name: str, coro_fn: Callable[[], Awaitable[str]]) -> None:
    """Run one job, logging start/success/failure with timestamps and
    recording the outcome to JobRunLog. Never raises - a job failure must
    never crash the scheduler or take down other scheduled jobs."""
    started_at = datetime.now(timezone.utc)
    name_he = JOB_NAMES_HE.get(job_name, job_name)
    logger.info("[JOB START] %s (%s) at %s", job_name, name_he, started_at.isoformat())

    try:
        summary_he = await coro_fn()
        finished_at = datetime.now(timezone.utc)
        duration = (finished_at - started_at).total_seconds()
        logger.info("[JOB SUCCESS] %s finished in %.1fs: %s", job_name, duration, summary_he)
        await store.record_job_run(job_name, started_at, finished_at, "success", summary_he)
    except Exception as exc:  # noqa: BLE001 - top-level guard, must never propagate
        finished_at = datetime.now(timezone.utc)
        duration = (finished_at - started_at).total_seconds()
        message_he = error_he(exc)
        logger.exception("[JOB FAILURE] %s failed after %.1fs: %s", job_name, duration, exc)
        await store.record_job_run(job_name, started_at, finished_at, "failure", message_he, error=str(exc))


# ---------------------------------------------------------------------------
# Job 1: continuous news polling (every 15-30 min)
# ---------------------------------------------------------------------------
async def _news_polling() -> str:
    analysis = await build_news_sentiment()
    await store.save_section(store.SECTION_NEWS, analysis)
    return f"סנטימנט שוק עודכן ({analysis.market_sentiment}): {analysis.headline_he}"


async def news_polling_job() -> None:
    await _run_job(JOB_NEWS_POLLING, _news_polling)


# ---------------------------------------------------------------------------
# Job 2: daily SEC filing scan + fundamentals-driven sections
# ---------------------------------------------------------------------------
async def _scan_new_filings(tickers: list[str]) -> int:
    """Checks each watchlist ticker's recent 10-K/10-Q filings against what
    the daily scan has seen before, logging (and counting) genuinely new
    ones. Sequential by design: this is a once-a-day background job, not a
    latency-sensitive request, and sequential calls naturally stay well
    within SEC EDGAR's rate-limit guidance without extra throttling code."""
    total_new = 0
    for ticker in tickers:
        for form_type in ("10-K", "10-Q"):
            try:
                response = await sec_service.get_recent_filings(ticker, form_type=form_type, limit=3)
            except Exception as exc:  # noqa: BLE001 - one ticker/form's failure shouldn't stop the scan
                logger.info("[JOB] %s: filing scan failed for %s %s: %s", JOB_DAILY_SCAN, ticker, form_type, exc)
                continue
            total_new += await store.mark_seen_and_count_new(ticker, response.filings)
    return total_new


async def _daily_report_scan() -> str:
    settings = get_settings()
    tickers = list(settings.watchlist_tickers)

    quotes = await fetch_quotes(tickers)
    facts = await fetch_facts(tickers)
    new_filings = await _scan_new_filings(tickers)

    parts = [f"נסרקו {len(tickers)} ניירות ברשימת המעקב ({new_filings} דיווחי SEC חדשים אותרו)."]
    successes = 0

    try:
        risk_alerts = await build_risk_alerts(tickers, quotes, facts)
        await store.save_section(store.SECTION_RISK, risk_alerts)
        parts.append(f"הערכות סיכון עודכנו ({len(risk_alerts)}).")
        successes += 1
    except Exception as exc:  # noqa: BLE001
        logger.warning("[JOB] %s: risk alerts section failed: %s", JOB_DAILY_SCAN, exc)
        parts.append(f"עדכון הערכות סיכון נכשל: {error_he(exc)}")

    try:
        reports = await build_company_reports(tickers, facts)
        await store.save_section(store.SECTION_REPORTS, reports)
        parts.append(f"ניתוחי דוחות כספיים עודכנו ({len(reports)}).")
        successes += 1
    except Exception as exc:  # noqa: BLE001
        logger.warning("[JOB] %s: company reports section failed: %s", JOB_DAILY_SCAN, exc)
        parts.append(f"עדכון ניתוחי דוחות נכשל: {error_he(exc)}")

    try:
        smallcap = await build_smallcap_opportunities(tickers, quotes, facts, settings.smallcap_market_cap_usd)
        await store.save_section(store.SECTION_SMALLCAP, smallcap)
        parts.append(f"הזדמנויות small-cap עודכנו ({len(smallcap)}).")
        successes += 1
    except Exception as exc:  # noqa: BLE001
        logger.warning("[JOB] %s: smallcap section failed: %s", JOB_DAILY_SCAN, exc)
        parts.append(f"עדכון סריקת small-cap נכשל: {error_he(exc)}")

    summary_he = " ".join(parts)
    if successes == 0:
        # Every section failed - this is a real job failure, not a partial
        # degradation, so it must be recorded as such in JobRunLog.
        raise AdvisorError("All daily-scan sections failed", summary_he, status_code=502)
    return summary_he


async def daily_report_scan_job() -> None:
    await _run_job(JOB_DAILY_SCAN, _daily_report_scan)
