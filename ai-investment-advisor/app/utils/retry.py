"""
Shared retry policy for outbound calls to external financial data APIs.

Network blips and transient 5xx/429 responses are retried with exponential
backoff; anything else (bad request, auth failure, not found) is allowed to
propagate immediately since retrying it would just waste quota.
"""
from __future__ import annotations

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in RETRYABLE_STATUS_CODES
    return False


def external_api_retry(attempts: int = 3):
    """Decorator factory: retry a coroutine/function up to `attempts` times."""
    return retry(
        reraise=True,
        stop=stop_after_attempt(attempts),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception(_is_retryable),
    )
