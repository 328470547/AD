from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.risk_assessor_agent import RiskAssessorAgent
from app.agents.schemas import RiskAssessment
from app.models.schemas import StockQuote
from datetime import datetime, timezone

SAMPLE_RESULT = RiskAssessment(
    ticker="XYZ",
    risk_level="גבוה",
    is_flagged=True,
    warning_headline_he="הפסדים מתמשכים ותזרים מזומנים שלילי",
    warning_detail_he="החברה מציגה הפסדים ברבעונים האחרונים לצד ירידה חדה במחיר המניה.",
    red_flags_he=["הפסד נקי", "תנודתיות קיצונית"],
    reasoning_he="בהתבסס על הנתונים הפיננסיים והתנודתיות במחיר, קיים סיכון גבוה.",
)


def _make_fake_llm(return_value):
    fake_structured = MagicMock()
    fake_structured.ainvoke = AsyncMock(return_value=return_value)
    fake_llm = MagicMock()
    fake_llm.with_structured_output.return_value = fake_structured
    return fake_llm


@pytest.mark.asyncio
async def test_assess_flags_high_risk_and_sets_ticker():
    quote = StockQuote(provider="yfinance", ticker="xyz", price=1.2, as_of=datetime.now(timezone.utc))
    with patch("app.agents.risk_assessor_agent.get_llm", return_value=_make_fake_llm(SAMPLE_RESULT)):
        agent = RiskAssessorAgent()
        result = await agent.assess("xyz", quote=quote, facts=None)
    assert result.is_flagged is True
    assert result.risk_level == "גבוה"
    assert result.ticker == "xyz"  # overwritten with the caller's ticker casing


@pytest.mark.asyncio
async def test_assess_handles_missing_data_gracefully():
    with patch("app.agents.risk_assessor_agent.get_llm", return_value=_make_fake_llm(SAMPLE_RESULT)):
        agent = RiskAssessorAgent()
        result = await agent.assess("NODATA", quote=None, facts=None, related_news=None)
    assert result.ticker == "NODATA"
