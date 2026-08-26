from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.report_analyzer_agent import ReportAnalyzerAgent
from app.agents.schemas import CompanyReportAnalysis
from app.models.schemas import CompanyFinancialFacts
from app.utils.errors import NoDataFoundError

SAMPLE_RESULT = CompanyReportAnalysis(
    ticker="ACME",
    financial_health="חזק",
    summary_he="החברה מציגה צמיחה יציבה בהכנסות לצד רווחיות גבוהה.",
    key_metrics_commentary_he="ההכנסות והרווח הנקי במגמת עלייה, ויחס ההתחייבויות לנכסים סביר.",
    reasoning_he="בהתבסס על הנתונים הפיננסיים, החברה נמצאת במצב יציב.",
    recommendation_he="ניתוח זה אינו מהווה ייעוץ השקעות מחייב; יש לבחון נתונים נוספים.",
)


def _make_fake_llm(return_value):
    fake_structured = MagicMock()
    fake_structured.ainvoke = AsyncMock(return_value=return_value)
    fake_llm = MagicMock()
    fake_llm.with_structured_output.return_value = fake_structured
    return fake_llm


@pytest.mark.asyncio
async def test_analyze_raises_not_found_without_facts():
    agent = ReportAnalyzerAgent()
    with pytest.raises(NoDataFoundError):
        await agent.analyze("ACME", facts=None)


@pytest.mark.asyncio
async def test_analyze_fills_in_ticker_and_company_name():
    facts = CompanyFinancialFacts(ticker="ACME", cik="0000000001", company_name="Acme Corp", revenue_usd=1_000_000)
    with patch("app.agents.report_analyzer_agent.get_llm", return_value=_make_fake_llm(SAMPLE_RESULT)):
        agent = ReportAnalyzerAgent()
        result = await agent.analyze("ACME", facts, filings=[])
    assert result.ticker == "ACME"
    assert result.company_name == "Acme Corp"
    assert result.financial_health == "חזק"
