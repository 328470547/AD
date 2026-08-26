from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.agents.schemas import DashboardSnapshot
from app.main import app

CACHED = DashboardSnapshot(generated_at=datetime.now(timezone.utc), watchlist=["AAPL"], source="cache")
LIVE = DashboardSnapshot(generated_at=datetime.now(timezone.utc), watchlist=["MSFT"], source="live")


def test_snapshot_endpoint_reads_cache_by_default():
    with patch("app.api.routes.analysis.snapshot_store.load_latest", new=AsyncMock(return_value=CACHED)), patch(
        "app.api.routes.analysis.build_dashboard_snapshot", new=AsyncMock(return_value=LIVE)
    ) as live_mock:
        with TestClient(app) as client:
            response = client.get("/api/dashboard/snapshot")
    assert response.status_code == 200
    assert response.json()["source"] == "cache"
    live_mock.assert_not_called()


def test_snapshot_endpoint_falls_back_to_live_when_nothing_cached_yet():
    """Fresh install / before the first scheduled job run: the dashboard
    must not be left empty just because no background job has completed."""
    with patch("app.api.routes.analysis.snapshot_store.load_latest", new=AsyncMock(return_value=None)), patch(
        "app.api.routes.analysis.build_dashboard_snapshot", new=AsyncMock(return_value=LIVE)
    ) as live_mock:
        with TestClient(app) as client:
            response = client.get("/api/dashboard/snapshot")
    assert response.status_code == 200
    assert response.json()["source"] == "live"
    live_mock.assert_called_once_with()


def test_snapshot_endpoint_uses_live_compute_for_explicit_ticker_override():
    with patch(
        "app.api.routes.analysis.snapshot_store.load_latest", new=AsyncMock(return_value=CACHED)
    ) as cache_mock, patch("app.api.routes.analysis.build_dashboard_snapshot", new=AsyncMock(return_value=LIVE)) as live_mock:
        with TestClient(app) as client:
            response = client.get("/api/dashboard/snapshot", params={"tickers": "MSFT"})
    assert response.status_code == 200
    assert response.json()["source"] == "live"
    live_mock.assert_called_once_with(["MSFT"])
    cache_mock.assert_not_called()


def test_scheduler_status_endpoint_returns_expected_shape():
    with TestClient(app) as client:
        response = client.get("/api/scheduler/status")
    assert response.status_code == 200
    data = response.json()
    assert set(data.keys()) >= {"enabled", "running", "jobs", "sections", "recent_runs"}
    # SCHEDULER_ENABLED=false in the test environment (tests/conftest.py),
    # so the scheduler is never started and reports no registered jobs.
    assert data["enabled"] is False
    assert data["jobs"] == []
