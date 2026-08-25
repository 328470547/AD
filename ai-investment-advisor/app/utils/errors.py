"""
Shared error types for the data-fetching layer.

Every exception carries two messages:
  * `message`    - technical, English, goes into logs.
  * `message_he` - user-facing, Hebrew, safe to return straight to the
                    frontend/dashboard so that ALL system output stays in
                    Hebrew, per the product requirement.
"""
from __future__ import annotations


class AdvisorError(Exception):
    """Base class for all application-raised errors."""

    def __init__(self, message: str, message_he: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.message = message
        self.message_he = message_he
        self.status_code = status_code

    def to_dict(self) -> dict:
        return {"error": self.message, "error_he": self.message_he}


class DataProviderRateLimitError(AdvisorError):
    """Raised when an upstream data provider throttles/rejects due to quota."""

    def __init__(self, provider: str) -> None:
        super().__init__(
            message=f"Rate limit exceeded for provider '{provider}'.",
            message_he=f"חריגה ממכסת הבקשות המותרת לספק הנתונים '{provider}'. נסה שוב מאוחר יותר.",
            status_code=429,
        )


class DataProviderUnavailableError(AdvisorError):
    """Raised when an upstream provider is unreachable or returns a server error."""

    def __init__(self, provider: str, detail: str = "") -> None:
        super().__init__(
            message=f"Provider '{provider}' unavailable: {detail}",
            message_he=f"ספק הנתונים '{provider}' אינו זמין כרגע. המערכת תנסה מקור נתונים חלופי.",
            status_code=503,
        )


class DataProviderConfigError(AdvisorError):
    """Raised when a required API key / configuration value is missing."""

    def __init__(self, provider: str) -> None:
        super().__init__(
            message=f"Missing API credentials for provider '{provider}'.",
            message_he=f"חסר מפתח API עבור הספק '{provider}'. יש להגדיר אותו בקובץ ההגדרות (.env).",
            status_code=500,
        )


class NoDataFoundError(AdvisorError):
    """Raised when a query legitimately returns no results (not an error state)."""

    def __init__(self, subject: str) -> None:
        super().__init__(
            message=f"No data found for '{subject}'.",
            message_he=f"לא נמצאו נתונים עבור '{subject}'.",
            status_code=404,
        )


class AllProvidersFailedError(AdvisorError):
    """Raised when both the primary and fallback providers have failed."""

    def __init__(self, resource: str, detail: str = "") -> None:
        super().__init__(
            message=f"All providers failed for resource '{resource}': {detail}",
            message_he=(
                f"לא ניתן היה לאחזר נתוני '{resource}' - כל מקורות הנתונים "
                "הזמינים נכשלו. אנא נסה שוב בעוד מספר דקות."
            ),
            status_code=502,
        )
