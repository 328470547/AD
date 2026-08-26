from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.news_sentiment_agent import NewsSentimentAgent
from app.agents.schemas import NewsSentimentAnalysis
from app.models.schemas import NewsArticle
from app.utils.errors import DataProviderUnavailableError, NoDataFoundError

SAMPLE_RESULT = NewsSentimentAnalysis(
    market_sentiment="חיובי",
    headline_he="השוק ממשיך לעלות על רקע נתוני תעסוקה חזקים",
    market_impact_summary_he="נתוני התעסוקה החזקים תומכים בהמשך עליות בשוק המניות.",
    key_drivers_he=["נתוני תעסוקה חזקים", "ציפיות להורדת ריבית"],
    affected_sectors_he=["טכנולוגיה", "פיננסים"],
    reasoning_he="בהתבסס על הכתבות, ניכר שהנתונים הכלכליים תומכים בסנטימנט חיובי.",
)


def _make_fake_llm(return_value=None, side_effect=None):
    fake_structured = MagicMock()
    fake_structured.ainvoke = AsyncMock(return_value=return_value, side_effect=side_effect)
    fake_llm = MagicMock()
    fake_llm.with_structured_output.return_value = fake_structured
    return fake_llm


@pytest.mark.asyncio
async def test_analyze_empty_articles_raises_not_found():
    agent = NewsSentimentAgent()
    with pytest.raises(NoDataFoundError):
        await agent.analyze([])


@pytest.mark.asyncio
async def test_analyze_returns_structured_hebrew_result():
    articles = [NewsArticle(provider="newsapi", title="Fed holds rates", summary="...", url="https://x")]
    with patch("app.agents.news_sentiment_agent.get_llm", return_value=_make_fake_llm(return_value=SAMPLE_RESULT)):
        agent = NewsSentimentAgent()
        result = await agent.analyze(articles)
    assert result.market_sentiment == "חיובי"
    assert result.headline_he


@pytest.mark.asyncio
async def test_analyze_wraps_llm_failure():
    articles = [NewsArticle(provider="newsapi", title="X", summary="", url="https://x")]
    with patch(
        "app.agents.news_sentiment_agent.get_llm", return_value=_make_fake_llm(side_effect=RuntimeError("boom"))
    ):
        agent = NewsSentimentAgent()
        with pytest.raises(DataProviderUnavailableError):
            await agent.analyze(articles)
