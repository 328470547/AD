from unittest.mock import AsyncMock, patch

import pytest

from app.agents.orchestrator import _build_risk_alerts
from app.agents.schemas import RiskAssessment
from app.utils.errors import DataProviderConfigError

SAMPLE_ASSESSMENT = RiskAssessment(
    ticker="AAPL",
    risk_level="נמוך",
    is_flagged=False,
    warning_headline_he="אין ממצאים חריגים",
    warning_detail_he="לא זוהו סיכונים מהותיים.",
    reasoning_he="בהתבסס על הנתונים, מצבה הפיננסי של החברה יציב.",
)


@pytest.mark.asyncio
async def test_build_risk_alerts_raises_when_every_assessment_fails():
    """Regression test: if the LLM is unreachable/misconfigured for every
    ticker, the section must surface an error - not silently look like
    'no risk detected', which would be actively misleading."""
    with patch(
        "app.agents.orchestrator.risk_assessor_agent.assess",
        new=AsyncMock(side_effect=DataProviderConfigError("anthropic")),
    ):
        with pytest.raises(Exception):
            await _build_risk_alerts(["AAPL", "MSFT"], quotes={}, facts={})


@pytest.mark.asyncio
async def test_build_risk_alerts_returns_partial_results_on_partial_failure():
    async def fake_assess(ticker, quote=None, facts=None):
        if ticker == "AAPL":
            return SAMPLE_ASSESSMENT
        raise DataProviderConfigError("anthropic")

    with patch("app.agents.orchestrator.risk_assessor_agent.assess", new=AsyncMock(side_effect=fake_assess)):
        results = await _build_risk_alerts(["AAPL", "MSFT"], quotes={}, facts={})

    assert len(results) == 1
    assert results[0].ticker == "AAPL"
