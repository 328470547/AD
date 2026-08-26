"""
LLM client factory for all four agents.

Provider is chosen via LLM_PROVIDER ("google" by default - the Gemini API
has a genuine free tier at https://aistudio.google.com/apikey, unlike
Anthropic's pay-per-token-only API; "anthropic" for Claude if you'd rather
pay for it). Both providers implement LangChain's standard
`with_structured_output`, so nothing in app/agents/*_agent.py needs to know
or care which one is actually running - swapping providers is a config
change, not a code change.

A single low-temperature instance per (provider, temperature) is reused
across agents - financial reasoning should be consistent and reproducible,
not creative.
"""
from __future__ import annotations

from functools import lru_cache

from langchain_core.language_models import BaseChatModel

from app.core.config import get_settings
from app.utils.errors import DataProviderConfigError


@lru_cache
def get_llm(temperature: float = 0.2) -> BaseChatModel:
    settings = get_settings()

    if settings.llm_provider == "google":
        if not settings.google_api_key:
            raise DataProviderConfigError("google")
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.google_api_key,
            temperature=temperature,
            max_tokens=2048,
            timeout=60,
            max_retries=2,
        )

    if not settings.anthropic_api_key:
        raise DataProviderConfigError("anthropic")
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(
        model=settings.anthropic_model,
        api_key=settings.anthropic_api_key,
        temperature=temperature,
        max_tokens=2048,
        timeout=60,
        max_retries=2,
    )
