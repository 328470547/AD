"""
Thin, cached client for the FastAPI backend (Phase 1-2 data services +
Phase 3 AI agents). Kept separate from app.py so the dashboard's rendering
code never touches HTTP details directly.

Every call raises `BackendError`, whose `.message_he` is always safe to show
directly in the UI (mirrors the backend's own AdvisorError contract).
"""
from __future__ import annotations

import os
from typing import Any, Optional

import httpx
import streamlit as st

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000").rstrip("/")
REQUEST_TIMEOUT = 90.0  # AI agent calls can take a while


class BackendError(Exception):
    def __init__(self, message_he: str) -> None:
        super().__init__(message_he)
        self.message_he = message_he


def _get(path: str, params: Optional[dict] = None) -> Any:
    url = f"{API_BASE_URL}{path}"
    try:
        response = httpx.get(url, params=params, timeout=REQUEST_TIMEOUT)
    except httpx.ConnectError as exc:
        raise BackendError(
            f"לא ניתן להתחבר לשרת ה-Backend בכתובת {API_BASE_URL}. "
            "ודאו שהשרת (uvicorn app.main:app) פעיל."
        ) from exc
    except httpx.TimeoutException as exc:
        raise BackendError("הבקשה לשרת נכשלה עקב פסק זמן (timeout). נסו שוב בעוד מספר שניות.") from exc
    except httpx.HTTPError as exc:
        raise BackendError(f"שגיאת תקשורת עם השרת: {exc}") from exc

    if response.status_code >= 400:
        try:
            payload = response.json()
            message = payload.get("error_he") or "אירעה שגיאה בלתי צפויה בשרת."
        except ValueError:
            message = f"שגיאת שרת (קוד {response.status_code})."
        raise BackendError(message)

    return response.json()


@st.cache_data(ttl=60, show_spinner=False)
def fetch_dashboard_snapshot(tickers_csv: Optional[str] = None) -> dict:
    params = {"tickers": tickers_csv} if tickers_csv else None
    return _get("/api/dashboard/snapshot", params=params)


@st.cache_data(ttl=30, show_spinner=False)
def fetch_health() -> dict:
    return _get("/health")


@st.cache_data(ttl=300, show_spinner=False)
def fetch_risk_assessment(ticker: str) -> dict:
    return _get(f"/api/analysis/risk/{ticker.strip().upper()}")


@st.cache_data(ttl=300, show_spinner=False)
def fetch_report_analysis(ticker: str) -> dict:
    return _get(f"/api/analysis/report/{ticker.strip().upper()}")


@st.cache_data(ttl=120, show_spinner=False)
def fetch_stock_quote(ticker: str) -> dict:
    return _get(f"/api/stocks/quote/{ticker.strip().upper()}")
