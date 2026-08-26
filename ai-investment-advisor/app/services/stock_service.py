"""
Real-time & historical stock price data.

Primary provider: yfinance (free, no API key). Since yfinance is a
synchronous/blocking library, calls are pushed to a worker thread so they
never block the FastAPI event loop.

Fallback provider: Polygon.io REST API (used automatically if yfinance
fails, or as primary if STOCK_DATA_PRIMARY_PROVIDER=polygon and a key is
configured).
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
import yfinance as yf
from cachetools import TTLCache

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.schemas import StockHistory, StockHistoryPoint, StockQuote
from app.utils.errors import (
    AllProvidersFailedError,
    DataProviderConfigError,
    DataProviderRateLimitError,
    DataProviderUnavailableError,
    NoDataFoundError,
)
from app.utils.retry import external_api_retry

logger = get_logger(__name__)

POLYGON_BASE_URL = "https://api.polygon.io"

# Quotes move fast; keep the cache TTL short just to absorb bursts of
# duplicate requests (e.g. a dashboard auto-refreshing several widgets).
_quote_cache: TTLCache = TTLCache(maxsize=512, ttl=30)
_history_cache: TTLCache = TTLCache(maxsize=256, ttl=300)


class StockService:
    def __init__(self) -> None:
        self.settings = get_settings()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def get_quote(self, ticker: str) -> StockQuote:
        ticker = ticker.strip().upper()
        cache_key = f"quote:{ticker}"
        if cache_key in _quote_cache:
            return _quote_cache[cache_key]

        providers = self._provider_order()
        last_error: Optional[Exception] = None

        for provider in providers:
            try:
                if provider == "yfinance":
                    quote = await self._get_quote_yfinance(ticker)
                else:
                    quote = await self._get_quote_polygon(ticker)
                _quote_cache[cache_key] = quote
                return quote
            except NoDataFoundError:
                raise
            except Exception as exc:  # noqa: BLE001 - deliberately broad, we fall back
                logger.warning("stock quote provider %s failed for %s: %s", provider, ticker, exc)
                last_error = exc
                continue

        raise AllProvidersFailedError("מחיר מניה", detail=str(last_error) if last_error else "")

    async def get_history(self, ticker: str, period: str = "1mo", interval: str = "1d") -> StockHistory:
        ticker = ticker.strip().upper()
        cache_key = f"history:{ticker}:{period}:{interval}"
        if cache_key in _history_cache:
            return _history_cache[cache_key]

        try:
            history = await self._get_history_yfinance(ticker, period, interval)
            _history_cache[cache_key] = history
            return history
        except NoDataFoundError:
            raise
        except Exception as yf_exc:  # noqa: BLE001
            logger.warning("yfinance history failed for %s: %s", ticker, yf_exc)
            if self.settings.polygon_api_key:
                try:
                    history = await self._get_history_polygon(ticker, period, interval)
                    _history_cache[cache_key] = history
                    return history
                except Exception as poly_exc:  # noqa: BLE001
                    raise AllProvidersFailedError("היסטוריית מניה", detail=str(poly_exc)) from poly_exc
            raise AllProvidersFailedError("היסטוריית מניה", detail=str(yf_exc)) from yf_exc

    # ------------------------------------------------------------------
    # yfinance
    # ------------------------------------------------------------------
    async def _get_quote_yfinance(self, ticker: str) -> StockQuote:
        info: dict[str, Any] = await asyncio.to_thread(self._fetch_yfinance_info, ticker)

        price = info.get("currentPrice") or info.get("regularMarketPrice")
        previous_close = info.get("previousClose") or info.get("regularMarketPreviousClose")
        if price is None:
            raise NoDataFoundError(ticker)

        change = None
        change_percent = None
        if price is not None and previous_close:
            change = price - previous_close
            change_percent = (change / previous_close) * 100 if previous_close else None

        return StockQuote(
            provider="yfinance",
            ticker=ticker,
            price=price,
            currency=info.get("currency", "USD"),
            change=change,
            change_percent=change_percent,
            day_high=info.get("dayHigh"),
            day_low=info.get("dayLow"),
            volume=info.get("volume"),
            market_cap=info.get("marketCap"),
            previous_close=previous_close,
            as_of=datetime.now(timezone.utc),
        )

    @staticmethod
    def _fetch_yfinance_info(ticker: str) -> dict[str, Any]:
        try:
            t = yf.Ticker(ticker)
            info = t.get_info()
        except Exception as exc:  # noqa: BLE001
            raise DataProviderUnavailableError("yfinance", str(exc)) from exc
        if not info or info.get("regularMarketPrice") is None and info.get("currentPrice") is None:
            # yfinance returns a near-empty dict for unknown tickers instead
            # of raising, so we translate that into our own not-found error.
            raise NoDataFoundError(ticker)
        return info

    async def _get_history_yfinance(self, ticker: str, period: str, interval: str) -> StockHistory:
        df = await asyncio.to_thread(self._fetch_yfinance_history, ticker, period, interval)
        if df is None or df.empty:
            raise NoDataFoundError(ticker)

        points = [
            StockHistoryPoint(
                date=idx.to_pydatetime(),
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=int(row["Volume"]),
            )
            for idx, row in df.iterrows()
        ]
        return StockHistory(provider="yfinance", ticker=ticker, period=period, interval=interval, points=points)

    @staticmethod
    def _fetch_yfinance_history(ticker: str, period: str, interval: str):
        try:
            t = yf.Ticker(ticker)
            return t.history(period=period, interval=interval)
        except Exception as exc:  # noqa: BLE001
            raise DataProviderUnavailableError("yfinance", str(exc)) from exc

    # ------------------------------------------------------------------
    # Polygon.io (fallback / optional primary)
    # ------------------------------------------------------------------
    @external_api_retry()
    async def _polygon_get(self, path: str, params: dict | None = None) -> dict:
        if not self.settings.polygon_api_key:
            raise DataProviderConfigError("polygon")
        params = dict(params or {})
        params["apiKey"] = self.settings.polygon_api_key
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{POLYGON_BASE_URL}{path}", params=params)
            if response.status_code == 429:
                raise DataProviderRateLimitError("polygon")
            response.raise_for_status()
            return response.json()

    async def _get_quote_polygon(self, ticker: str) -> StockQuote:
        data = await self._polygon_get(f"/v2/aggs/ticker/{ticker}/prev")
        results = data.get("results") or []
        if not results:
            raise NoDataFoundError(ticker)
        bar = results[0]
        price = bar.get("c")
        prev_close = bar.get("o")
        change = price - prev_close if price is not None and prev_close is not None else None
        change_percent = (change / prev_close * 100) if change is not None and prev_close else None
        return StockQuote(
            provider="polygon",
            ticker=ticker,
            price=price,
            currency="USD",
            change=change,
            change_percent=change_percent,
            day_high=bar.get("h"),
            day_low=bar.get("l"),
            volume=bar.get("v"),
            previous_close=prev_close,
            as_of=datetime.now(timezone.utc),
        )

    async def _get_history_polygon(self, ticker: str, period: str, interval: str) -> StockHistory:
        # Minimal mapping from yfinance-style period/interval to Polygon's
        # range aggregates endpoint; good enough as a fallback path.
        multiplier, timespan, from_date, to_date = self._polygon_range_params(period, interval)
        data = await self._polygon_get(
            f"/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from_date}/{to_date}",
            params={"sort": "asc", "limit": 5000},
        )
        results = data.get("results") or []
        if not results:
            raise NoDataFoundError(ticker)
        points = [
            StockHistoryPoint(
                date=datetime.fromtimestamp(bar["t"] / 1000, tz=timezone.utc),
                open=bar["o"],
                high=bar["h"],
                low=bar["l"],
                close=bar["c"],
                volume=int(bar["v"]),
            )
            for bar in results
        ]
        return StockHistory(provider="polygon", ticker=ticker, period=period, interval=interval, points=points)

    @staticmethod
    def _polygon_range_params(period: str, interval: str) -> tuple[int, str, str, str]:
        from datetime import timedelta

        period_days = {
            "1d": 1, "5d": 5, "1mo": 30, "3mo": 90, "6mo": 180,
            "1y": 365, "2y": 730, "5y": 1825, "ytd": 365, "max": 3650,
        }.get(period, 30)
        timespan_map = {"1d": "day", "1h": "hour", "5m": "minute", "1wk": "week", "1mo": "month"}
        timespan = timespan_map.get(interval, "day")

        to_date = datetime.now(timezone.utc).date()
        from_date = to_date - timedelta(days=period_days)
        return 1, timespan, from_date.isoformat(), to_date.isoformat()

    # ------------------------------------------------------------------
    def _provider_order(self) -> list[str]:
        primary = self.settings.stock_data_primary_provider
        others = [p for p in ("yfinance", "polygon") if p != primary]
        return [primary, *others]


stock_service = StockService()
