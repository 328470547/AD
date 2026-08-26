import pytest
import respx
from httpx import Response

from app.core.config import get_settings
from app.services.news_service import ALPHA_VANTAGE_BASE_URL, NEWSAPI_BASE_URL, NewsService
from app.utils.errors import AllProvidersFailedError


@pytest.fixture(autouse=True)
def _configure_keys(monkeypatch):
    monkeypatch.setattr(get_settings().__class__, "newsapi_key", "test-newsapi-key", raising=False)
    settings = get_settings()
    settings.newsapi_key = "test-newsapi-key"
    settings.alpha_vantage_key = "test-av-key"
    settings.news_primary_provider = "newsapi"
    yield


@pytest.mark.asyncio
@respx.mock
async def test_get_financial_news_uses_primary_provider():
    respx.get(f"{NEWSAPI_BASE_URL}/everything").mock(
        return_value=Response(
            200,
            json={
                "articles": [
                    {
                        "title": "Fed holds rates steady",
                        "description": "The Federal Reserve kept interest rates unchanged.",
                        "url": "https://example.com/a1",
                        "source": {"name": "Reuters"},
                        "publishedAt": "2026-08-20T12:00:00Z",
                    }
                ]
            },
        )
    )
    service = NewsService()
    result = await service.get_financial_news(query="fed rates", page_size=5)
    assert result.provider_used == "newsapi"
    assert len(result.articles) == 1
    assert result.articles[0].title == "Fed holds rates steady"


@pytest.mark.asyncio
@respx.mock
async def test_falls_back_to_alpha_vantage_on_rate_limit():
    respx.get(f"{NEWSAPI_BASE_URL}/everything").mock(return_value=Response(429))
    respx.get(ALPHA_VANTAGE_BASE_URL).mock(
        return_value=Response(
            200,
            json={
                "feed": [
                    {
                        "title": "Tech stocks rally",
                        "summary": "Growth stocks led gains today.",
                        "url": "https://example.com/a2",
                        "source": "Bloomberg",
                        "time_published": "20260820T120000",
                        "overall_sentiment_score": 0.35,
                        "ticker_sentiment": [{"ticker": "AAPL"}],
                    }
                ]
            },
        )
    )
    service = NewsService()
    result = await service.get_financial_news(query="tech stocks", page_size=5)
    assert result.provider_used == "alpha_vantage"
    assert result.articles[0].tickers == ["AAPL"]
    assert result.articles[0].sentiment_score == 0.35


@pytest.mark.asyncio
@respx.mock
async def test_all_providers_failed_raises():
    respx.get(f"{NEWSAPI_BASE_URL}/everything").mock(return_value=Response(500))
    respx.get(ALPHA_VANTAGE_BASE_URL).mock(return_value=Response(500))
    service = NewsService()
    with pytest.raises(AllProvidersFailedError):
        await service.get_financial_news(query="unique-uncached-query-xyz", page_size=5)
