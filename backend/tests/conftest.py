import os

# Dev/test default. Tests override get_llm explicitly, so this only guards against a stray .env.
os.environ.setdefault("LLM_PROVIDER", "fake")

from collections.abc import AsyncIterator  # noqa: E402
from typing import Any  # noqa: E402

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker  # noqa: E402

import app.companion.models  # noqa: E402,F401  (registers tables)
from app.companion.llm import FakeLLM, get_llm  # noqa: E402
from app.core.db import Base, get_session, make_engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest_asyncio.fixture
async def db(tmp_path) -> AsyncIterator[async_sessionmaker]:  # type: ignore[type-arg]
    """Fresh temp SQLite database per test. Yields a session factory."""
    url = f"sqlite+aiosqlite:///{(tmp_path / 'test.db').as_posix()}"
    engine = make_engine(url)  # production engine settings: WAL, busy timeout, hide_parameters
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
def llm_box() -> dict[str, Any]:
    """Mutable holder so a test can swap the LLM the app's get_llm dependency returns."""
    return {"llm": FakeLLM()}


@pytest_asyncio.fixture
async def client(db, llm_box) -> AsyncIterator[AsyncClient]:  # type: ignore[no-untyped-def]
    async def override_session() -> AsyncIterator[Any]:
        async with db() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_llm] = lambda: llm_box["llm"]
    try:
        # ASGITransport does not run lifespan, so the schema is created by the db fixture above.
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
            yield http
    finally:
        app.dependency_overrides.clear()
