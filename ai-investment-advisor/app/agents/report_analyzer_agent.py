"""
Daily Financial Report Analysis agent (task 3): turns SEC XBRL fundamentals
+ recent filing metadata into a Hebrew fundamental-health analysis.
"""
from __future__ import annotations

from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.llm import get_llm
from app.agents.prompts import REPORT_ANALYZER_SYSTEM_PROMPT_HE
from app.agents.schemas import CompanyReportAnalysis
from app.core.logging import get_logger
from app.models.schemas import CompanyFinancialFacts, SecFiling
from app.utils.errors import DataProviderUnavailableError, NoDataFoundError

logger = get_logger(__name__)


class ReportAnalyzerAgent:
    async def analyze(
        self,
        ticker: str,
        facts: Optional[CompanyFinancialFacts],
        filings: Optional[list[SecFiling]] = None,
    ) -> CompanyReportAnalysis:
        if facts is None:
            raise NoDataFoundError(f"נתונים פיננסיים עבור {ticker}")

        llm = get_llm(temperature=0.2).with_structured_output(CompanyReportAnalysis)
        data_block = self._format_data(ticker, facts, filings or [])

        messages = [
            SystemMessage(content=REPORT_ANALYZER_SYSTEM_PROMPT_HE),
            HumanMessage(content=f"נתח את הבריאות הפיננסית של {ticker} על סמך הנתונים הבאים:\n\n{data_block}"),
        ]

        try:
            result = await llm.ainvoke(messages)
        except Exception as exc:  # noqa: BLE001
            logger.warning("report analyzer agent failed for %s: %s", ticker, exc)
            raise DataProviderUnavailableError("anthropic", str(exc)) from exc

        result.ticker = ticker
        if not result.company_name:
            result.company_name = facts.company_name
        return result

    @staticmethod
    def _format_data(ticker: str, facts: CompanyFinancialFacts, filings: list[SecFiling]) -> str:
        parts = [
            f"טיקר: {ticker}",
            f"שם חברה: {facts.company_name or 'לא ידוע'}",
            f"שנת/תקופת דיווח: {facts.fiscal_year} ({facts.fiscal_period})",
            f"הכנסות (USD): {facts.revenue_usd}",
            f"רווח נקי (USD): {facts.net_income_usd}",
            f"סך נכסים (USD): {facts.total_assets_usd}",
            f"סך התחייבויות (USD): {facts.total_liabilities_usd}",
            f"מזומן ושווי מזומן (USD): {facts.cash_and_equivalents_usd}",
            f"רווח בסיסי למניה (EPS): {facts.eps_basic}",
        ]
        if facts.total_assets_usd and facts.total_liabilities_usd:
            ratio = facts.total_liabilities_usd / facts.total_assets_usd if facts.total_assets_usd else None
            parts.append(f"יחס התחייבויות לנכסים (מחושב): {ratio:.2f}" if ratio is not None else "")

        if filings:
            filing_lines = "\n".join(
                f"  - {f.form_type} הוגש בתאריך {f.filed_at.date() if f.filed_at else 'לא ידוע'}: {f.filing_url}"
                for f in filings[:5]
            )
            parts.append(f"דיווחים רגולטוריים אחרונים:\n{filing_lines}")

        return "\n".join(p for p in parts if p)


report_analyzer_agent = ReportAnalyzerAgent()
