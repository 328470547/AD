"""
AI Investment Advisor - backend entrypoint (Phase 1-2: data services API).

All JSON responses are emitted with ensure_ascii=False so Hebrew text (error
messages now, AI-generated analysis from Phase 3 onward) is transmitted as
real UTF-8 characters instead of \\uXXXX escapes.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import news, sec, stocks
from app.core.config import get_settings
from app.core.database import init_db
from app.core.logging import configure_logging, get_logger
from app.utils.errors import AdvisorError

configure_logging()
logger = get_logger(__name__)
settings = get_settings()


class UTF8JSONResponse(JSONResponse):
    def render(self, content) -> bytes:
        import json

        return json.dumps(content, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting AI Investment Advisor API (env=%s)", settings.app_env)
    await init_db()
    yield
    logger.info("Shutting down AI Investment Advisor API")


app = FastAPI(
    title="AI Investment Advisor - שירותי נתונים",
    description="שירותי אחזור נתונים (חדשות, מניות, דיווחי SEC) עבור פלטפורמת הייעוץ ההשקעתי מבוסס-AI",
    version="0.1.0",
    default_response_class=UTF8JSONResponse,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AdvisorError)
async def advisor_error_handler(request: Request, exc: AdvisorError) -> UTF8JSONResponse:
    logger.error("AdvisorError on %s: %s", request.url.path, exc.message)
    return UTF8JSONResponse(status_code=exc.status_code, content=exc.to_dict())


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> UTF8JSONResponse:
    logger.exception("Unhandled error on %s", request.url.path)
    return UTF8JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "error_he": "אירעה שגיאה בלתי צפויה במערכת. הצוות הטכני קיבל התראה.",
        },
    )


app.include_router(news.router)
app.include_router(stocks.router)
app.include_router(sec.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "status_he": "המערכת פעילה", "env": settings.app_env}
