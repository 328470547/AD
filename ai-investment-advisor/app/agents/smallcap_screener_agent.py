"""
Small-Cap/Penny Stock Screener agent (task 4): given a set of candidate
tickers with price + fundamentals, identifies and ranks the ones with the
most promising growth potential, in Hebrew, with reasoning per pick.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.llm import get_llm
from app.agents.prompts import SMALLCAP_SCREENER_SYSTEM_PROMPT_HE
from app.agents.schemas import SmallCapOpportunity, SmallCapScreenerResult
from app.core.logging import get_logger
from app.models.schemas import CompanyFinancialFacts, StockQuote
from app.utils.errors import DataProviderUnavailableError, NoDataFoundError

logger = get_logger(__name__)


@dataclass
class ScreenerCandidate:
    ticker: str
    quote: Optional[StockQuote] = None
    facts: Optional[CompanyFinancialFacts] = None
    company_name: str = ""


class SmallCapScreenerAgent:
    async def screen(
        self, candidates: list[ScreenerCandidate], market_cap_threshold_usd: float
    ) -> list[SmallCapOpportunity]:
        small_caps = [
            c for c in candidates if c.quote and c.quote.market_cap and c.quote.market_cap < market_cap_threshold_usd
        ]
        if not small_caps:
            raise NoDataFoundError("מועמדות small-cap העונות לסף שווי השוק")

        llm = get_llm(temperature=0.3).with_structured_output(SmallCapScreenerResult)
        data_block = self._format_candidates(small_caps)

        messages = [
            SystemMessage(content=SMALLCAP_SCREENER_SYSTEM_PROMPT_HE),
            HumanMessage(
                content=(
                    "להלן רשימת חברות small-cap מועמדות. דרג ותאר את ההזדמנויות "
                    f"המבטיחות ביותר (עד 5 חברות):\n\n{data_block}"
                )
            ),
        ]

        try:
            result = await llm.ainvoke(messages)
        except Exception as exc:  # noqa: BLE001
            logger.warning("smallcap screener agent failed: %s", exc)
            raise DataProviderUnavailableError("anthropic", str(exc)) from exc

        opportunities = sorted(result.opportunities, key=lambda o: o.opportunity_score, reverse=True)
        return opportunities

    @staticmethod
    def _format_candidates(candidates: list[ScreenerCandidate]) -> str:
        lines = []
        for c in candidates:
            facts_str = ""
            if c.facts:
                facts_str = (
                    f", הכנסות={c.facts.revenue_usd}, רווח נקי={c.facts.net_income_usd}, "
                    f"מזומן={c.facts.cash_and_equivalents_usd}"
                )
            lines.append(
                f"- {c.ticker} ({c.company_name}): מחיר={c.quote.price if c.quote else 'לא ידוע'}, "
                f"שווי שוק={c.quote.market_cap if c.quote else 'לא ידוע'}, "
                f"שינוי יומי={c.quote.change_percent if c.quote else 'לא ידוע'}%{facts_str}"
            )
        return "\n".join(lines)


smallcap_screener_agent = SmallCapScreenerAgent()
