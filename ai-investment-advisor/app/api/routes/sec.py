from __future__ import annotations

from fastapi import APIRouter, Query

from app.models.schemas import CompanyFinancialFacts, SecFilingsResponse
from app.services.sec_service import sec_service

router = APIRouter(prefix="/api/sec", tags=["sec"])


@router.get("/filings/{ticker}", response_model=SecFilingsResponse)
async def get_filings(
    ticker: str,
    form_type: str = Query("10-K", description="10-K, 10-Q, 8-K"),
    limit: int = Query(5, ge=1, le=25),
) -> SecFilingsResponse:
    return await sec_service.get_recent_filings(ticker, form_type=form_type, limit=limit)


@router.get("/company-facts/{ticker}", response_model=CompanyFinancialFacts)
async def get_company_facts(ticker: str) -> CompanyFinancialFacts:
    """Key XBRL financial-health figures (revenue, net income, assets,
    liabilities, cash, EPS) extracted from the latest 10-K."""
    return await sec_service.get_company_facts(ticker)
