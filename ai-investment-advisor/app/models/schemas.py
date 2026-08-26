"""
Pydantic response models shared by the data services and the API layer.

Field names stay in English (for programmatic/frontend use), but any
free-text description intended for end users is documented as Hebrew output
once the AI analysis layer (Phase 3) populates it.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class NewsArticle(BaseModel):
    provider: str
    title: str
    summary: str = ""
    url: str
    source: str = ""
    published_at: Optional[datetime] = None
    tickers: list[str] = Field(default_factory=list)
    sentiment_score: Optional[float] = None  # -1 (very negative) .. 1 (very positive)


class NewsResponse(BaseModel):
    query: str
    provider_used: str
    articles: list[NewsArticle]
    fetched_at: datetime


class StockQuote(BaseModel):
    provider: str
    ticker: str
    price: Optional[float] = None
    currency: str = "USD"
    change: Optional[float] = None
    change_percent: Optional[float] = None
    day_high: Optional[float] = None
    day_low: Optional[float] = None
    volume: Optional[int] = None
    market_cap: Optional[float] = None
    previous_close: Optional[float] = None
    as_of: datetime


class StockHistoryPoint(BaseModel):
    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


class StockHistory(BaseModel):
    provider: str
    ticker: str
    period: str
    interval: str
    points: list[StockHistoryPoint]


class SecFiling(BaseModel):
    provider: str
    ticker: str
    cik: str = ""
    company_name: str = ""
    form_type: Literal["10-K", "10-Q", "8-K", "OTHER"]
    filed_at: Optional[datetime] = None
    filing_url: str
    accession_no: str = ""


class SecFilingsResponse(BaseModel):
    ticker: str
    provider_used: str
    filings: list[SecFiling]
    fetched_at: datetime


class CompanyFinancialFacts(BaseModel):
    """Key figures pulled from SEC XBRL company-facts, used later (Phase 3)
    as the raw input for Hebrew-language fundamental analysis."""

    ticker: str
    cik: str
    company_name: str = ""
    revenue_usd: Optional[float] = None
    net_income_usd: Optional[float] = None
    total_assets_usd: Optional[float] = None
    total_liabilities_usd: Optional[float] = None
    cash_and_equivalents_usd: Optional[float] = None
    eps_basic: Optional[float] = None
    fiscal_year: Optional[int] = None
    fiscal_period: Optional[str] = None


class ErrorResponse(BaseModel):
    error: str
    error_he: str
