"""
Async database layer used as a caching/persistence tier for fetched market
data, news and SEC filings.

Encoding note: SQLite and PostgreSQL both default to UTF-8, but we are
explicit about it everywhere it matters (the SQLite connect URL, and the
recommendation for Postgres below) so Hebrew AI-generated text can never be
mis-stored or mis-rendered.

  Postgres production URL example (charset is negotiated via the driver,
  but keep the DB itself created with UTF-8 encoding):
    postgresql+asyncpg://user:pass@host:5432/advisor
    # created with: CREATE DATABASE advisor WITH ENCODING 'UTF8' ...
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.config import get_settings

settings = get_settings()

_connect_args = {}
if settings.database_url.startswith("sqlite"):
    # Ensure the sqlite3 driver talks UTF-8 text I/O explicitly.
    _connect_args = {"check_same_thread": False}
    # sqlite won't create missing parent directories on its own.
    _sqlite_path = settings.database_url.split("///", 1)[-1]
    if _sqlite_path and _sqlite_path != ":memory:":
        Path(_sqlite_path).resolve().parent.mkdir(parents=True, exist_ok=True)

engine = create_async_engine(
    settings.database_url,
    echo=False,
    connect_args=_connect_args,
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class NewsArticleCache(Base):
    __tablename__ = "news_article_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(32))
    query: Mapped[str] = mapped_column(String(256))
    title: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(String(1024))
    source: Mapped[str] = mapped_column(String(256), default="")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_json: Mapped[str] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class StockQuoteCache(Base):
    __tablename__ = "stock_quote_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(32))
    ticker: Mapped[str] = mapped_column(String(16), index=True)
    price: Mapped[float] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    raw_json: Mapped[str] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SecFilingCache(Base):
    __tablename__ = "sec_filing_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(32))
    ticker: Mapped[str] = mapped_column(String(16), index=True)
    cik: Mapped[str] = mapped_column(String(16), default="")
    form_type: Mapped[str] = mapped_column(String(16))
    filed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    filing_url: Mapped[str] = mapped_column(String(1024))
    raw_json: Mapped[str] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:  # pragma: no cover - simple DI helper
    async with AsyncSessionLocal() as session:
        yield session
