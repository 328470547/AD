"""
Central application configuration.

All settings are loaded from environment variables / a local .env file via
pydantic-settings. Nothing here should ever contain a real secret - see
.env.example for the list of variables an operator needs to supply.
"""
from __future__ import annotations

from functools import lru_cache
from typing import List, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"

    # --- Market data ---------------------------------------------------
    polygon_api_key: str = ""
    stock_data_primary_provider: Literal["yfinance", "polygon"] = "yfinance"

    # --- News ------------------------------------------------------------
    newsapi_key: str = ""
    alpha_vantage_key: str = ""
    news_primary_provider: Literal["newsapi", "alpha_vantage"] = "newsapi"

    # --- SEC filings -------------------------------------------------------
    sec_api_key: str = ""
    sec_edgar_user_agent: str = "AI Investment Advisor contact@example.com"

    # --- AI engine (Phase 3) ------------------------------------------------
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-sonnet-latest"

    # Tickers the AI agents monitor by default (risk alerts, small-cap
    # screener, daily report analysis) when the caller doesn't supply its
    # own list. A real deployment would replace this with a proper market
    # scanner; this is a curated demo universe covering large caps and a
    # few small-cap/penny names so the screener has something to find.
    watchlist_tickers: List[str] = Field(
        default_factory=lambda: [
            "AAPL", "MSFT", "NVDA", "TSLA", "GME", "PLTR", "SOFI", "IONQ", "RIOT", "MARA",
        ]
    )
    smallcap_market_cap_usd: float = 2_000_000_000  # screener threshold: below this = "small-cap"

    @field_validator("watchlist_tickers", mode="before")
    @classmethod
    def _split_watchlist(cls, value: object) -> object:
        if isinstance(value, str):
            return [t.strip().upper() for t in value.split(",") if t.strip()]
        return value

    # --- Database ------------------------------------------------------------
    database_url: str = "sqlite+aiosqlite:///./data/app.db"

    # --- Scheduling / caching ---------------------------------------------
    redis_url: str = "redis://localhost:6379/0"

    # --- API server ------------------------------------------------------------
    cors_origins: List[str] = Field(default_factory=lambda: ["http://localhost:8501"])

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (singleton for the process lifetime)."""
    return Settings()
