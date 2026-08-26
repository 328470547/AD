from __future__ import annotations

from fastapi import APIRouter, Query

from app.models.schemas import StockHistory, StockQuote
from app.services.stock_service import stock_service

router = APIRouter(prefix="/api/stocks", tags=["stocks"])


@router.get("/quote/{ticker}", response_model=StockQuote)
async def get_quote(ticker: str) -> StockQuote:
    """Real-time (delayed per provider terms) quote for a single ticker."""
    return await stock_service.get_quote(ticker)


@router.get("/history/{ticker}", response_model=StockHistory)
async def get_history(
    ticker: str,
    period: str = Query("1mo", description="1d,5d,1mo,3mo,6mo,1y,2y,5y,ytd,max"),
    interval: str = Query("1d", description="5m,1h,1d,1wk,1mo"),
) -> StockHistory:
    return await stock_service.get_history(ticker, period=period, interval=interval)
