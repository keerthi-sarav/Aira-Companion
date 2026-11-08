import json
from datetime import timedelta

import pytest
from sqlalchemy import select, update

from app.companion import engine
from app.companion.errors import CompanionPaused
from app.companion.engine import reply
from app.companion.llm import LLMResult, OpenAICompatLLM
from app.companion.models import CompanionEndUser, CompanionMessage, CompanionPendingTurn, utcnow
from app.companion.schemas import ToolCall
from app.core.config import get_settings
from helpers import BASE, TENANT_A, TENANT_B, hdr, make_companion, post_test_chat, set_status

CHART_TOOL = {
    "name": "get_chart",
    "description": "Fetch the birth chart from the app",
    "parameters": {"type": "object", "properties": {}},
}


class MoodLLM:
    """Replies with a mood tag only when the user's message asks for one."""

    configured = True

    def __init__(self):
        self.calls: list[list[dict]] = []

    async def chat(self, messages, *, tools=None, **_):
        self.calls.append(messages)
        last = messages[-1]["content"]
        if "happy" in last:
            return LLMResult(text="[mood: happy] Glad to hear it.")
        if "worried" in last:
            return LLMResult(text="[mood:concerned] Let's slow down together.")
        return LLMResult(text="Tell me more.")


class ToolForeverLLM:
    """Asks for a tool whenever tools are offered. Used to prove the 3-round cap."""

    configured = True

    def __init__(self):
        self.tools_seen: list = []

    async def chat(self, messages, *, tools=None, **_):
        self.tools_seen.append(tools)
        if tools:
            return LLMResult(
                text=None,
                tool_calls=[ToolCall(id=f"c{len(self.tools_seen)}", name="get_chart", args={})],
            )
        return LLMResult(text="[mood: calm] Final answer.")


class BrokenLLM:
    configured = True

    async def chat(self, messages, *, tools=None, **_):
        raise RuntimeError("upstream exploded")


async def _pause_with_chart(client, companion_id: str) -> dict:
    response = await post_test_chat(client, companion_id, "Show my chart please", tools=[CHART_TOOL])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "tool_call"
    return body


# ---------- pause flow ----------

async def test_tool_pause_flow_end_to_end_and_tool_output_is_not_persisted(client, db, llm_box):
    companion = await make_companion(client)
    paused = await _pause_with_chart(client, companion["id"])
    [call] = paused["tool_calls"]
    assert call["name"] == "get_chart" and call["args"] == {}
    assert paused["turn_id"]

    done = await client.post(
        f"{BASE}/test-chat/continue",
        json={
            "turn_id": paused["turn_id"],
            "results": [{"id": call["id"], "output": {"sun": "SECRET_CHART_42"}}],
        },
        headers=hdr(),
    )
    assert done.status_code == 200, done.text
    body = done.json()
    assert body["status"] == "done"
    assert body["mood"] == "warm"
    assert "Show my chart please" in body["text"]

    # The LLM saw the assistant tool_calls message and the tool result in OpenAI shape.
    messages = llm_box["llm"].calls[-1]["messages"]
    assistant_msg, tool_msg = messages[-2], messages[-1]
    assert assistant_msg["role"] == "assistant"
    assert assistant_msg["tool_calls"][0]["id"] == call["id"]
    assert assistant_msg["tool_calls"][0]["type"] == "function"
    assert assistant_msg["tool_calls"][0]["function"]["name"] == "get_chart"
    assert tool_msg["role"] == "tool"
    assert tool_msg["tool_call_id"] == call["id"]
    assert "SECRET_CHART_42" in tool_msg["content"]

    async with db() as session:
        rows = (await session.execute(select(CompanionMessage))).scalars().all()
        assert rows, "expected stored messages"
        for row in rows:
            assert "SECRET_CHART_42" not in row.content
            assert "SECRET_CHART_42" not in json.dumps(row.tool_calls)
        assistant_rows = [row for row in rows if row.role == "assistant"]
        assert len(assistant_rows) == 1
        assert assistant_rows[0].tool_calls == [{"name": "get_chart", "args": {}}]
        pending = (await session.execute(select(CompanionPendingTurn))).scalars().all()
        assert pending == []


async def test_slot_is_released_before_tool_call_is_returned(client, llm_box):
    companion = await make_companion(client)
    await _pause_with_chart(client, companion["id"])
    assert engine._semaphore()._value == get_settings().COMPANION_MAX_CONCURRENT


async def test_unknown_turn_is_404(client):
    response = await client.post(
        f"{BASE}/test-chat/continue",
        json={"turn_id": "does-not-exist", "results": []},
        headers=hdr(),
    )
    assert response.status_code == 404
    assert response.json()["error"] == "turn_expired"


async def test_expired_turn_is_404_and_swept(client, db):
    companion = await make_companion(client)
    paused = await _pause_with_chart(client, companion["id"])
    async with db() as session:
        await session.execute(
            update(CompanionPendingTurn)
            .where(CompanionPendingTurn.id == paused["turn_id"])
            .values(expires_at=utcnow() - timedelta(seconds=1))
        )
        await session.commit()

    response = await client.post(
        f"{BASE}/test-chat/continue",
        json={"turn_id": paused["turn_id"], "results": []},
        headers=hdr(),
    )
    assert response.status_code == 404
    assert response.json()["error"] == "turn_expired"
    async with db() as session:
        assert (await session.execute(select(CompanionPendingTurn))).scalars().all() == []


async def test_other_tenant_cannot_continue_a_turn(client):
    companion = await make_companion(client, TENANT_A)
    paused = await _pause_with_chart(client, companion["id"])
    response = await client.post(
        f"{BASE}/test-chat/continue",
        json={"turn_id": paused["turn_id"], "results": []},
        headers=hdr(TENANT_B),
    )
    assert response.status_code == 404
    assert response.json()["error"] == "turn_expired"


async def test_three_round_cap_sends_round_three_without_tools(client, llm_box):
    llm = ToolForeverLLM()
    llm_box["llm"] = llm
    companion = await make_companion(client)

    first = await post_test_chat(client, companion["id"], "chart please", tools=[CHART_TOOL])
    assert first.json()["status"] == "tool_call"

    second = await client.post(
        f"{BASE}/test-chat/continue",
        json={"turn_id": first.json()["turn_id"], "results": [{"id": "c1", "output": {}}]},
        headers=hdr(),
    )
    assert second.json()["status"] == "tool_call"

    third = await client.post(
        f"{BASE}/test-chat/continue",
        json={"turn_id": second.json()["turn_id"], "results": [{"id": "c2", "output": {}}]},
        headers=hdr(),
    )
    body = third.json()
    assert body["status"] == "done"
    assert body["text"] == "Final answer."
    assert len(llm.tools_seen) == 3
    assert llm.tools_seen[0] and llm.tools_seen[1]
    assert llm.tools_seen[2] is None


async def test_missing_tool_result_gets_tool_unavailable(client, llm_box):
    companion = await make_companion(client)
    paused = await _pause_with_chart(client, companion["id"])
    await client.post(
        f"{BASE}/test-chat/continue",
        json={"turn_id": paused["turn_id"], "results": []},
        headers=hdr(),
    )
    tool_msg = llm_box["llm"].calls[-1]["messages"][-1]
    assert tool_msg["role"] == "tool"
    assert tool_msg["content"] == "tool unavailable"


# ---------- paused, draft, misconfigured, busy ----------

async def test_paused_companion_blocks_reply_while_draft_test_chat_works(client, db, llm_box):
    companion = await make_companion(client)
    cid = companion["id"]

    # Draft: real-traffic reply is blocked, test-chat is allowed.
    async with db() as session:
        with pytest.raises(CompanionPaused):
            await reply(session, cid, TENANT_A, "end-user-9", "hello", llm=llm_box["llm"])
    assert (await post_test_chat(client, cid, "draft hello")).status_code == 200

    await set_status(client, cid, "paused")
    blocked = await post_test_chat(client, cid, "paused hello")
    assert blocked.status_code == 409
    assert blocked.json()["error"] == "companion_paused"

    await set_status(client, cid, "live")
    async with db() as session:
        live = await reply(session, cid, TENANT_A, "end-user-9", "live hello", llm=llm_box["llm"])
    assert live.status == "done"


async def test_unknown_companion_is_404(client):
    response = await post_test_chat(client, "00000000-0000-0000-0000-000000000000", "hi")
    assert response.status_code == 404
    assert response.json()["error"] == "companion_not_found"


async def test_misconfigured_llm_is_422(client, llm_box):
    llm_box["llm"] = OpenAICompatLLM(base_url="https://example.invalid/v1", api_key="", model="m")
    companion = await make_companion(client)
    response = await post_test_chat(client, companion["id"], "hi")
    assert response.status_code == 422
    assert response.json()["error"] == "companion_misconfigured"
    assert "Settings" in response.json()["message"]


async def test_busy_when_all_slots_are_taken(client, monkeypatch):
    monkeypatch.setattr(engine, "SLOT_WAIT_SECONDS", 0.05)
    companion = await make_companion(client)
    semaphore = engine._semaphore()
    slots = get_settings().COMPANION_MAX_CONCURRENT
    for _ in range(slots):
        await semaphore.acquire()
    try:
        response = await post_test_chat(client, companion["id"], "hi")
        assert response.status_code == 503
        assert response.json()["error"] == "companion_busy"
    finally:
        for _ in range(slots):
            semaphore.release()


async def test_llm_failure_sends_fallback_and_keeps_mood(client, llm_box):
    llm_box["llm"] = BrokenLLM()
    companion = await make_companion(client, fallback_line="Konjam wait pannunga.")
    response = await post_test_chat(client, companion["id"], "hi")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "done"
    assert body["text"] == "Konjam wait pannunga."
    assert body["mood"] == "calm"


# ---------- mood, conversations, memory of history ----------

async def test_mood_persists_across_messages(client, llm_box):
    llm = MoodLLM()
    llm_box["llm"] = llm
    companion = await make_companion(client)
    cid = companion["id"]

    first = (await post_test_chat(client, cid, "I am happy today")).json()
    assert first["mood"] == "happy" and first["text"] == "Glad to hear it."

    # No tag in this reply: the previous mood is kept and the text is unchanged.
    second = (await post_test_chat(client, cid, "tell me more")).json()
    assert second["mood"] == "happy"
    assert second["text"] == "Tell me more."
    assert "Your current mood with this user: happy." in llm.calls[-1][0]["content"]

    third = (await post_test_chat(client, cid, "I am worried")).json()
    assert third["mood"] == "concerned"

    fourth = (await post_test_chat(client, cid, "ok")).json()
    assert fourth["mood"] == "concerned"
    assert "Your current mood with this user: concerned." in llm.calls[-1][0]["content"]


async def test_separate_conversations_per_companion_for_same_person(client, llm_box):
    companion_a = await make_companion(client, name="Jothidar AI")
    companion_b = await make_companion(client, name="Vastu Guru", industry="general")

    reply_a = (await post_test_chat(client, companion_a["id"], "hello from A")).json()
    reply_b = (await post_test_chat(client, companion_b["id"], "hello from B")).json()
    assert reply_a["conversation_id"] != reply_b["conversation_id"]

    history_a = (await client.get(f"{BASE}/{companion_a['id']}/test-chat/history", headers=hdr())).json()
    history_b = (await client.get(f"{BASE}/{companion_b['id']}/test-chat/history", headers=hdr())).json()
    assert [m["content"] for m in history_a] == ["hello from A", "(echo) hello from A"]
    assert [m["content"] for m in history_b] == ["hello from B", "(echo) hello from B"]

    # B's prompt must not carry A's chat.
    b_prompt = " ".join(m["content"] for m in llm_box["llm"].calls[-1]["messages"])
    assert "from A" not in b_prompt

    # A's next prompt carries A's own history.
    await post_test_chat(client, companion_a["id"], "second to A")
    a_prompt = llm_box["llm"].calls[-1]["messages"]
    assert any(m["role"] == "user" and m["content"] == "hello from A" for m in a_prompt)
    assert not any("from B" in m["content"] for m in a_prompt)


async def test_forget_me_wipes_all_companions_of_tenant_only(client, db, llm_box):
    llm_box["llm"] = MoodLLM()
    companion_a = await make_companion(client, TENANT_A, name="Jothidar AI")
    companion_b = await make_companion(client, TENANT_A, name="Vastu Guru")
    other = await make_companion(client, TENANT_B, name="Jothidar AI")

    for companion in (companion_a, companion_b):
        assert (await post_test_chat(client, companion["id"], "I am happy")).json()["mood"] == "happy"
    other_reply = await post_test_chat(client, other["id"], "I am happy", tenant=TENANT_B)
    assert other_reply.json()["mood"] == "happy"

    forget = await client.post(f"{BASE}/end-users/owner-test:owner-1/forget", headers=hdr(TENANT_A))
    assert forget.status_code == 204

    for companion in (companion_a, companion_b):
        history = await client.get(f"{BASE}/{companion['id']}/test-chat/history", headers=hdr(TENANT_A))
        assert history.json() == []

    other_history = await client.get(f"{BASE}/{other['id']}/test-chat/history", headers=hdr(TENANT_B))
    assert len(other_history.json()) == 2

    async with db() as session:
        users = (
            await session.execute(select(CompanionEndUser).where(CompanionEndUser.tenant_id == TENANT_A))
        ).scalars().all()
        assert len(users) == 1
        assert users[0].display_name is None
        assert users[0].forgotten_at is not None

    # Next message starts fresh with the default mood.
    fresh = (await post_test_chat(client, companion_a["id"], "hello again")).json()
    assert fresh["mood"] == "calm"
    assert "Your current mood with this user: calm." in llm_box["llm"].calls[-1][0]["content"]


async def test_forget_for_unknown_person_is_204(client):
    response = await client.post(f"{BASE}/end-users/nobody/forget", headers=hdr())
    assert response.status_code == 204
