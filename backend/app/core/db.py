from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

# How long a connection waits for SQLite's write lock before failing with "database is locked".
SQLITE_BUSY_TIMEOUT_SECONDS = 15


class Base(DeclarativeBase):
    pass


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def make_engine(url: str, *, sqlite_busy_timeout: float = SQLITE_BUSY_TIMEOUT_SECONDS) -> AsyncEngine:
    """Build the engine. hide_parameters keeps bound values (message text) out of exception strings.

    For SQLite files: WAL journaling, and a busy timeout on every connection so concurrent writers wait
    instead of failing. Writers should still commit quickly; the engine must not hold the lock during LLM calls.
    """
    kwargs: dict[str, Any] = {"pool_pre_ping": True, "hide_parameters": True}
    is_sqlite = url.startswith("sqlite")
    if is_sqlite:
        kwargs["connect_args"] = {"timeout": sqlite_busy_timeout}
    engine = create_async_engine(url, **kwargs)
    if is_sqlite:
        busy_ms = int(sqlite_busy_timeout * 1000)

        @event.listens_for(engine.sync_engine, "connect")
        def _sqlite_pragmas(dbapi_connection: Any, _record: Any) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute(f"PRAGMA busy_timeout={busy_ms}")  # first, so the WAL switch below can wait too
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

    return engine


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = make_engine(get_settings().DATABASE_URL)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _session_factory


async def get_session() -> AsyncIterator[AsyncSession]:
    """Request-scoped session. Writers commit explicitly; uncommitted work is rolled back on close."""
    async with get_session_factory()() as session:
        yield session


async def dispose_engine() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
