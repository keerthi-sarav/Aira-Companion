"""Concurrency: slow LLM calls must not hold the DB write lock, and a paused turn can be resumed only once."""

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

import app.companion.models  # noqa: F401  (registers tables)
from app.companion.llm import FakeLLM, get_llm
from app.core.db import Base, get_session, make_engine
from app.main import app
from helpers import BASE, TENANT_A, hdr, make_companion, post_test_chat

LLM_SECONDS = 1.0
# Production waits 15 s for the SQLite write lock. This test waits 0.5 s, so a lock held across the
# 1 s LLM call fails fast with "database is locked" instead of quietly queuing.
LOCK_BUDGET_SECONDS = 0.5

CHART_TOOL = {
    "name": "get_chart",
    "description": "Fetch the birth chart from the app",
    "parameters": {"type": "object", "properties": {}},
}


class SlowLLM(FakeLLM):
    async def chat(self, messages, **kwargs):  # type: ignore[no-untyped-def]
        await asyncio.sleep(LLM_SECONDS)
        return await super().chat(messages, **kwargs)


@pytest_asyncio.fixture
async def slow_client(tmp_path, llm_box) -> AsyncIterator[AsyncClient]:  # type: ignore[no-untyped-def]
    """File-backed SQLite with a short lock budget. Errors surface as 500 responses, not exceptions."""
    url = f"sqlite+aiosqlite:///{(tmp_path / 'slow.db').as_posix()}"
    engine = make_engine(url, sqlite_busy_timeout=LOCK_BUDGET_SECONDS)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_session() -> AsyncIterator[Any]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_llm] = lambda: llm_box["llm"]
    try:
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as http:
            yield http
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()


async def test_three_concurrent_test_chats_from_different_users_all_succeed(slow_client, llm_box):
    llm_box["llm"] = SlowLLM()
    companion = await make_companion(slow_client)
    responses = await asyncio.gather(
        *(
            slow_client.post(
                f"{BASE}/{companion['id']}/test-chat",
                json={"message": f"hello from user {i}"},
                headers=hdr(TENANT_A, f"owner-{i}"),
            )
            for i in range(3)
        )
    )
    assert [r.status_code for r in responses] == [200, 200, 200], [r.text for r in responses]
    assert all(r.json()["status"] == "done" for r in responses)


async def test_two_concurrent_continues_on_one_turn_yield_one_200_and_one_404(client):
    companion = await make_companion(client)
    paused = (await post_test_chat(client, companion["id"], "Show my chart please", tools=[CHART_TOOL])).json()
    assert paused["status"] == "tool_call"
    [call] = paused["tool_calls"]
    body = {"turn_id": paused["turn_id"], "results": [{"id": call["id"], "output": {"sun": "Leo"}}]}

    responses = await asyncio.gather(
        *(client.post(f"{BASE}/test-chat/continue", json=body, headers=hdr()) for _ in range(2))
    )
    assert sorted(r.status_code for r in responses) == [200, 404], [r.text for r in responses]
    loser = next(r for r in responses if r.status_code == 404)
    assert loser.json()["error"] == "turn_expired"
