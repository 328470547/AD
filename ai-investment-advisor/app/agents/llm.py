"""
Claude 3.5 Sonnet client factory (via langchain-anthropic).

A single low-temperature instance is reused across agents - financial
reasoning should be consistent and reproducible, not creative.
"""
from __future__ import annotations

from functools import lru_cache

from langchain_anthropic import ChatAnthropic

from app.core.config import get_settings
from app.utils.errors import DataProviderConfigError


@lru_cache
def get_llm(temperature: float = 0.2) -> ChatAnthropic:
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise DataProviderConfigError("anthropic")
    return ChatAnthropic(
        model=settings.anthropic_model,
        api_key=settings.anthropic_api_key,
        temperature=temperature,
        max_tokens=2048,
        timeout=60,
        max_retries=2,
    )
