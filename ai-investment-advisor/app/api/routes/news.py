from __future__ import annotations

from fastapi import APIRouter, Query

from app.models.schemas import NewsResponse
from app.services.news_service import news_service

router = APIRouter(prefix="/api/news", tags=["news"])


@router.get("/financial", response_model=NewsResponse)
async def get_financial_news(
    query: str = Query("stock market OR earnings OR federal reserve", description="Search query"),
    page_size: int = Query(20, ge=1, le=100),
) -> NewsResponse:
    """Latest global financial news, normalized across providers.
    Hebrew-language impact summaries are added by the AI analysis layer
    (Phase 3) on top of this raw feed."""
    return await news_service.get_financial_news(query=query, page_size=page_size)
