"""
Risk Management & Warnings agent (task 5 from the product spec): explicitly
flags companies/sectors that look like high-risk or bad investments right
now, in Hebrew, with concrete red flags and full reasoning.
"""
from __future__ import annotations

from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.llm import get_llm
from app.agents.prompts import RISK_ASSESSOR_SYSTEM_PROMPT_HE
from app.agents.schemas import RiskAssessment
from app.core.logging import get_logger
from app.models.schemas import CompanyFinancialFacts, NewsArticle, StockQuote
from app.utils.errors import DataProviderUnavailableError

logger = get_logger(__name__)


class RiskAssessorAgent:
    async def assess(
        self,
        ticker: str,
        quote: Optional[StockQuote] = None,
        facts: Optional[CompanyFinancialFacts] = None,
        related_news: Optional[list[NewsArticle]] = None,
    ) -> RiskAssessment:
        llm = get_llm(temperature=0.15).with_structured_output(RiskAssessment)
        data_block = self._format_data(ticker, quote, facts, related_news or [])

        messages = [
            SystemMessage(content=RISK_ASSESSOR_SYSTEM_PROMPT_HE),
            HumanMessage(content=f"הערך את רמת הסיכון בהשקעה בנייר {ticker} על סמך הנתונים הבאים:\n\n{data_block}"),
        ]

        try:
            result = await llm.ainvoke(messages)
        except Exception as exc:  # noqa: BLE001
            logger.warning("risk assessor agent failed for %s: %s", ticker, exc)
            raise DataProviderUnavailableError("anthropic", str(exc)) from exc

        result.ticker = ticker
        return result

    @staticmethod
    def _format_data(
        ticker: str,
        quote: Optional[StockQuote],
        facts: Optional[CompanyFinancialFacts],
        related_news: list[NewsArticle],
    ) -> str:
        parts = [f"טיקר: {ticker}"]

        if quote:
            parts.append(
                "נתוני מחיר: "
                f"מחיר={quote.price}, שינוי יומי={quote.change_percent}%, "
                f"שווי שוק={quote.market_cap}, מחיר שיא יומי={quote.day_high}, "
                f"מחיר שפל יומי={quote.day_low}, ווליום={quote.volume}"
            )
        else:
            parts.append("נתוני מחיר: לא זמינים")

        if facts:
            parts.append(
                "נתונים פיננסיים (מהדוח השנתי האחרון): "
                f"הכנסות={facts.revenue_usd}, רווח נקי={facts.net_income_usd}, "
                f"נכסים={facts.total_assets_usd}, התחייבויות={facts.total_liabilities_usd}, "
                f"מזומן={facts.cash_and_equivalents_usd}, רווח למניה={facts.eps_basic}, "
                f"שנת דיווח={facts.fiscal_year}"
            )
        else:
            parts.append("נתונים פיננסיים: לא זמינים")

        if related_news:
            news_lines = "\n".join(f"  - {a.title}: {a.summary}" for a in related_news[:8])
            parts.append(f"חדשות רלוונטיות אחרונות:\n{news_lines}")
        else:
            parts.append("חדשות רלוונטיות: אין חדשות זמינות")

        return "\n".join(parts)


risk_assessor_agent = RiskAssessorAgent()
