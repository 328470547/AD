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
