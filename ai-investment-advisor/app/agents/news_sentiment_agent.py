"""
News Sentiment Predictor - turns a batch of raw news articles into a Hebrew
market-impact narrative and forecast-relevant sentiment signal (task 1 & 2
from the product spec: news aggregation + market trend/sentiment forecast).
"""
from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.llm import get_llm
from app.agents.prompts import NEWS_SENTIMENT_SYSTEM_PROMPT_HE
from app.agents.schemas import NewsSentimentAnalysis
from app.core.logging import get_logger
from app.models.schemas import NewsArticle
from app.utils.errors import DataProviderUnavailableError, NoDataFoundError

logger = get_logger(__name__)

MAX_ARTICLES = 15


class NewsSentimentAgent:
    async def analyze(self, articles: list[NewsArticle]) -> NewsSentimentAnalysis:
        if not articles:
            raise NoDataFoundError("חדשות לניתוח סנטימנט")

        llm = get_llm(temperature=0.2).with_structured_output(NewsSentimentAnalysis)
        articles_text = self._format_articles(articles[:MAX_ARTICLES])

        messages = [
            SystemMessage(content=NEWS_SENTIMENT_SYSTEM_PROMPT_HE),
            HumanMessage(
                content=(
                    "להלן רשימת כתבות חדשות פיננסיות עדכניות. נתח את הסנטימנט הכללי "
                    "ואת ההשפעה הפוטנציאלית שלהן על השוק:\n\n" + articles_text
                )
            ),
        ]

        try:
            result = await llm.ainvoke(messages)
        except Exception as exc:  # noqa: BLE001
            logger.warning("news sentiment agent failed: %s", exc)
            raise DataProviderUnavailableError("anthropic", str(exc)) from exc

        return result

    @staticmethod
    def _format_articles(articles: list[NewsArticle]) -> str:
        lines = []
        for i, article in enumerate(articles, start=1):
            sentiment_note = f" (ציון סנטימנט גולמי: {article.sentiment_score})" if article.sentiment_score is not None else ""
            lines.append(
                f"{i}. [{article.source or 'לא ידוע'}] {article.title}\n   {article.summary}{sentiment_note}"
            )
        return "\n".join(lines)


news_sentiment_agent = NewsSentimentAgent()
