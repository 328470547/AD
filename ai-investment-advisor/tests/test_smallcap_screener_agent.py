from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.schemas import SmallCapOpportunity, SmallCapScreenerResult
from app.agents.smallcap_screener_agent import ScreenerCandidate, SmallCapScreenerAgent
from app.models.schemas import StockQuote
from app.utils.errors import NoDataFoundError
from datetime import datetime, timezone

SAMPLE_RESULT = SmallCapScreenerResult(
    opportunities=[
        SmallCapOpportunity(
            ticker="SMLC",
            company_name="Small Cap Inc",
            market_cap_usd=500_000_000,
            growth_thesis_he="החברה מציגה צמיחה מהירה בשוק נישתי מתפתח.",
            reasoning_he="קצב הצמיחה ברבעונים האחרונים גבוה משמעותית מהממוצע בענף.",
            key_risks_he=["תחרות גוברת", "תלות בלקוח בודד"],
            opportunity_score=8,
        )
    ]
)


def _make_fake_llm(return_value):
    fake_structured = MagicMock()
    fake_structured.ainvoke = AsyncMock(return_value=return_value)
    fake_llm = MagicMock()
    fake_llm.with_structured_output.return_value = fake_structured
    return fake_llm


def _quote(ticker: str, market_cap: float) -> StockQuote:
    return StockQuote(provider="yfinance", ticker=ticker, price=5.0, market_cap=market_cap, as_of=datetime.now(timezone.utc))


@pytest.mark.asyncio
async def test_screen_raises_when_no_candidates_below_threshold():
    candidates = [ScreenerCandidate(ticker="BIG", quote=_quote("BIG", 500_000_000_000))]
    agent = SmallCapScreenerAgent()
    with pytest.raises(NoDataFoundError):
        await agent.screen(candidates, market_cap_threshold_usd=2_000_000_000)


@pytest.mark.asyncio
async def test_screen_filters_and_ranks_opportunities():
    candidates = [
        ScreenerCandidate(ticker="BIG", quote=_quote("BIG", 500_000_000_000)),
        ScreenerCandidate(ticker="SMLC", quote=_quote("SMLC", 500_000_000), company_name="Small Cap Inc"),
    ]
    with patch("app.agents.smallcap_screener_agent.get_llm", return_value=_make_fake_llm(SAMPLE_RESULT)):
        agent = SmallCapScreenerAgent()
        result = await agent.screen(candidates, market_cap_threshold_usd=2_000_000_000)
    assert len(result) == 1
    assert result[0].ticker == "SMLC"
    assert result[0].opportunity_score == 8
