"""
Real-time financial news aggregation.

Primary provider: NewsAPI.org ("everything" endpoint, filtered to business
sources). Fallback provider: Alpha Vantage NEWS_SENTIMENT, which
conveniently also returns a raw sentiment score we surface as-is (Phase 3
turns this into a full Hebrew narrative; this layer just normalizes data).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import httpx
from cachetools import TTLCache

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.schemas import NewsArticle, NewsResponse
from app.utils.errors import (
    AllProvidersFailedError,
    DataProviderConfigError,
    DataProviderRateLimitError,
    DataProviderUnavailableError,
)
from app.utils.retry import external_api_retry

logger = get_logger(__name__)

NEWSAPI_BASE_URL = "https://newsapi.org/v2"
ALPHA_VANTAGE_BASE_URL = "https://www.alphavantage.co/query"

_news_cache: TTLCache = TTLCache(maxsize=128, ttl=120)


class NewsService:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def get_financial_news(
        self, query: str = "stock market OR earnings OR federal reserve", page_size: int = 20
    ) -> NewsResponse:
        cache_key = f"{query}:{page_size}"
        if cache_key in _news_cache:
            return _news_cache[cache_key]

        providers = self._provider_order()
        last_error: Optional[Exception] = None

        for provider in providers:
            try:
                if provider == "newsapi":
                    articles = await self._fetch_newsapi(query, page_size)
                else:
                    articles = await self._fetch_alpha_vantage(query, page_size)
                response = NewsResponse(
                    query=query,
                    provider_used=provider,
                    articles=articles,
                    fetched_at=datetime.now(timezone.utc),
                )
                _news_cache[cache_key] = response
                return response
            except Exception as exc:  # noqa: BLE001 - fall back to next provider
                logger.warning("news provider %s failed: %s", provider, exc)
                last_error = exc
                continue

        raise AllProvidersFailedError("חדשות פיננסיות", detail=str(last_error) if last_error else "")

    # ------------------------------------------------------------------
    # NewsAPI.org
    # ------------------------------------------------------------------
    @external_api_retry()
    async def _fetch_newsapi(self, query: str, page_size: int) -> list[NewsArticle]:
        if not self.settings.newsapi_key:
            raise DataProviderConfigError("newsapi")

        params = {
            "q": query,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": min(page_size, 100),
            "apiKey": self.settings.newsapi_key,
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{NEWSAPI_BASE_URL}/everything", params=params)
            if response.status_code == 429:
                raise DataProviderRateLimitError("newsapi")
            if response.status_code >= 500:
                raise DataProviderUnavailableError("newsapi", f"status {response.status_code}")
            response.raise_for_status()
            data = response.json()

        articles = []
        for item in data.get("articles", []):
            published_at = None
            if item.get("publishedAt"):
                try:
                    published_at = datetime.fromisoformat(item["publishedAt"].replace("Z", "+00:00"))
                except ValueError:
                    published_at = None
            articles.append(
                NewsArticle(
                    provider="newsapi",
                    title=item.get("title") or "",
                    summary=item.get("description") or "",
                    url=item.get("url") or "",
                    source=(item.get("source") or {}).get("name", ""),
                    published_at=published_at,
                )
            )
        return articles

    # ------------------------------------------------------------------
    # Alpha Vantage NEWS_SENTIMENT (fallback)
    # ------------------------------------------------------------------
    @external_api_retry()
    async def _fetch_alpha_vantage(self, query: str, page_size: int) -> list[NewsArticle]:
        if not self.settings.alpha_vantage_key:
            raise DataProviderConfigError("alpha_vantage")

        params = {
            "function": "NEWS_SENTIMENT",
            "topics": "financial_markets",
            "limit": min(page_size, 200),
            "apikey": self.settings.alpha_vantage_key,
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(ALPHA_VANTAGE_BASE_URL, params=params)
            if response.status_code == 429:
                raise DataProviderRateLimitError("alpha_vantage")
            response.raise_for_status()
            data = response.json()

        # Alpha Vantage reports quota/config errors as HTTP 200 with a
        # "Note"/"Information" field instead of a real error status.
        if "Note" in data or "Information" in data:
            raise DataProviderRateLimitError("alpha_vantage")

        articles = []
        for item in data.get("feed", []):
            published_at = None
            raw_ts = item.get("time_published")
            if raw_ts:
                try:
                    published_at = datetime.strptime(raw_ts, "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
                except ValueError:
                    published_at = None
            tickers = [t.get("ticker") for t in item.get("ticker_sentiment", []) if t.get("ticker")]
            articles.append(
                NewsArticle(
                    provider="alpha_vantage",
                    title=item.get("title") or "",
                    summary=item.get("summary") or "",
                    url=item.get("url") or "",
                    source=item.get("source") or "",
                    published_at=published_at,
                    tickers=tickers,
                    sentiment_score=item.get("overall_sentiment_score"),
                )
            )
        return articles

    def _provider_order(self) -> list[str]:
        primary = self.settings.news_primary_provider
        others = [p for p in ("newsapi", "alpha_vantage") if p != primary]
        return [primary, *others]


news_service = NewsService()
