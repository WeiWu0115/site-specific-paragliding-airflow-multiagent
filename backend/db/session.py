"""
Async SQLAlchemy session factory and FastAPI dependency for paraglide-backend.

Provides the AsyncEngine, AsyncSessionLocal, and a get_db() dependency that
yields a database session per request with automatic cleanup.
"""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from loguru import logger
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from config.settings import get_settings

_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Return the application-level async database engine (lazy-initialized)."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            echo=(settings.log_level == "DEBUG"),
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
        )
        logger.info(f"Database engine created for: {settings.database_url.split('@')[-1]}")
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the application-level async session factory (lazy-initialized)."""
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=True,
            autocommit=False,
        )
    return _async_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an async DB session per request.

    Usage::

        @app.get("/example")
        async def example(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(MyModel))
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Type alias for use in route signatures
DatabaseDep = Annotated[AsyncSession, Depends(get_db)]
