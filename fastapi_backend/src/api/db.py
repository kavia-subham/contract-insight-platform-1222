"""
Database setup and session management for the Contract Insights API.

This module configures SQLAlchemy with async support, reads the database URL
from environment via core.config Settings, and exposes a dependency for
getting an async session in FastAPI routes. It also provides a Base declarative
for models to inherit from.
"""
from __future__ import annotations

import asyncio
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .core.config import get_settings


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for models."""


# Configure async engine and session maker
_settings = get_settings()

def _normalize_async_dsn(url: str | None) -> str:
    """
    Ensure the SQLAlchemy URL uses async drivers.

    - For PostgreSQL: enforce postgresql+asyncpg://
    - For SQLite: enforce sqlite+aiosqlite://
    - If no URL is provided, fallback to local sqlite+aiosqlite dev DB.
    """
    if not url or not url.strip():
        return "sqlite+aiosqlite:///./dev.db"

    u = url.strip()

    # Normalize common postgres prefixes to asyncpg
    # Support both 'postgresql://' and 'postgres://'
    if u.startswith("postgresql://"):
        u = "postgresql+asyncpg://" + u[len("postgresql://"):]
    elif u.startswith("postgres://"):
        u = "postgresql+asyncpg://" + u[len("postgres://"):]

    # Normalize sqlite URLs to aiosqlite
    if u.startswith("sqlite://") and not u.startswith("sqlite+aiosqlite://"):
        u = "sqlite+aiosqlite://" + u[len("sqlite://"):]

    return u

# Expect POSTGRES_URL in asyncpg form, e.g. postgresql+asyncpg://user:pass@host:5432/db
# If a non-async DSN is provided, normalize it to the appropriate async driver.
_normalized_url = _normalize_async_dsn(_settings.POSTGRES_URL)

engine: AsyncEngine = create_async_engine(
    _normalized_url,
    echo=False,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
    class_=AsyncSession,
)


# PUBLIC_INTERFACE
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide an async DB session as a FastAPI dependency."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            # Explicit close not necessary; context manager handles it.
            ...


async def init_models() -> None:
    """Create database tables if they do not exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def init_models_sync() -> None:
    """Synchronous wrapper to run async create_all at startup."""
    asyncio.get_event_loop().run_until_complete(init_models())
