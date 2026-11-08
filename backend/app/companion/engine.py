"""Reply engine (ARCHITECTURE.md sections 6 and 7). reply() starts a turn, continue_reply() resumes a paused one."""

import asyncio
import json
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.companion import prompt, store
from app.companion.errors import (
    CompanionBusy,
    CompanionMisconfigured,
    CompanionNotFound,
    CompanionPaused,
    TurnExpired,
)
from app.companion.knowledge import knowledge_provider
from app.companion.llm import LLMClient, LLMResult, app_tools_to_openai, get_llm
from app.companion.memory import memory_provider
from app.companion.mood import parse_mood
from app.companion.models import Companion, CompanionConversation, CompanionPendingTurn, utcnow
from app.companion.schemas import (
    MESSAGE_MAX_CHARS,
    TOOL_OUTPUT_MAX_CHARS,
    AppTool,
    CompanionReply,
    ToolCall,
    ToolResult,
)
from app.core.config import get_settings

log = logging.getLogger("aira.companion.engine")

MAX_ROUNDS = 3  # round 3 is sent without tools so the model must answer
HISTORY_LIMIT = 10
MAX_TOKENS = 700
TEMPERATURE = 0.5
SLOT_WAIT_SECONDS = 5
UNAVAILABLE_TOOL_OUTPUT = "tool unavailable"

# Semaphore is created lazily and rebuilt if the running event loop changes (tests create one loop per test).
_slot_state: dict[str, Any] = {"loop": None, "semaphore": None}


def _semaphore() -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    if _slot_state["loop"] is not loop or _slot_state["semaphore"] is None:
        _slot_state["loop"] = loop
        _slot_state["semaphore"] = asyncio.Semaphore(get_settings().COMPANION_MAX_CONCURRENT)
    return _slot_state["semaphore"]


async def _acquire_slot() -> asyncio.Semaphore:
    semaphore = _semaphore()
    try:
        await asyncio.wait_for(semaphore.acquire(), SLOT_WAIT_SECONDS)
    except TimeoutError as exc:
        raise CompanionBusy() from exc
    return semaphore


async def _gather_context(tenant_id: str, companion: Companion, end_user_id: str, message: str) -> tuple[str, str]:
    """Knowledge and memory run in parallel. Any failure degrades to empty context."""

    async def knowledge() -> str:
        try:
            return await knowledge_provider.get_context(tenant_id, message, companion.knowledge_tag_id) or ""
        except Exception as exc:
            log.warning("knowledge lookup failed (%s)", type(exc).__name__)
            return ""

    async def memory() -> str:
        try:
            return await memory_provider.context_for(companion.id, end_user_id, message) or ""
        except Exception as exc:
            log.warning("memory lookup failed (%s)", type(exc).__name__)
            return ""

    kb_context, memory_context = await asyncio.gather(knowledge(), memory())
    return kb_context, memory_context


async def _chat(llm: LLMClient, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None) -> LLMResult | None:
    """None means the call failed. The caller then sends the companion's fallback line."""
    try:
        return await llm.chat(
            messages,
            tools=tools or None,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            purpose="companion_reply",
        )
    except Exception as exc:
        log.warning("companion LLM call failed (%s)", type(exc).__name__)
        return None


def _apply_results(messages: list[dict[str, Any]], results: list[ToolResult]) -> list[dict[str, Any]]:
    """Append one role=tool message per pending tool call, in OpenAI shape."""
    pending_ids: list[str] = []
    for message in reversed(messages):
        if message.get("role") == "assistant" and message.get("tool_calls"):
            pending_ids = [call["id"] for call in message["tool_calls"]]
            break
    by_id = {result.id: result for result in results}
    updated = list(messages)
    for call_id in pending_ids:
        result = by_id.get(call_id)
        if result is None:
            content = UNAVAILABLE_TOOL_OUTPUT
        else:
            content = json.dumps(result.output, ensure_ascii=False, default=str)[:TOOL_OUTPUT_MAX_CHARS]
        updated.append({"role": "tool", "tool_call_id": call_id, "content": content})
    return updated


def _calls_log(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Tool names and args only, for companion_messages.tool_calls. Never output."""
    calls: list[dict[str, Any]] = []
    for message in messages:
        if message.get("role") != "assistant":
            continue
        for call in message.get("tool_calls") or []:
            function = call["function"]
            try:
                args = json.loads(function.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            calls.append({"name": function["name"], "args": args if isinstance(args, dict) else {}})
    return calls


async def _conclude(
    session: AsyncSession,
    tenant_id: str,
    companion: Companion,
    conversation: CompanionConversation,
    messages: list[dict[str, Any]],
    result: LLMResult | None,
    tools_offered: list[dict[str, Any]],
    round_no: int,
) -> CompanionReply:
    """Steps 7-9: pause for tools, or parse the mood and save the reply."""
    allowed_names = {tool["function"]["name"] for tool in tools_offered}
    requested = [call for call in (result.tool_calls if result else []) if call.name in allowed_names]

    if requested:
        assistant_message = {
            "role": "assistant",
            "content": (result.text if result else None) or None,
            "tool_calls": [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {"name": call.name, "arguments": json.dumps(call.args, ensure_ascii=False)},
                }
                for call in requested
            ],
        }
        turn = await store.create_pending_turn(
            session,
            tenant_id,
            companion.id,
            conversation.id,
            [*messages, assistant_message],
            tools_offered,
            round_no,
        )
        await session.commit()
        return CompanionReply(
            status="tool_call",
            conversation_id=conversation.id,
            turn_id=turn.id,
            tool_calls=[ToolCall(id=c.id, name=c.name, args=c.args) for c in requested],
        )

    raw = result.text.strip() if result and result.text else ""
    if raw:
        text, mood = parse_mood(raw, conversation.mood)
    else:
        text, mood = "", conversation.mood
    if not text.strip():
        text = companion.fallback_line
    text = text[:MESSAGE_MAX_CHARS]

    calls = _calls_log(messages)
    saved = await store.add_message(
        session, conversation, "assistant", text, mood=mood, tool_calls=calls or None
    )
    conversation.mood = mood
    await session.commit()
    return CompanionReply(
        status="done",
        text=text,
        mood=mood,
        conversation_id=conversation.id,
        message_id=saved.id,
    )


async def reply(
    session: AsyncSession,
    companion_id: str,
    tenant_id: str,
    external_user_id: str,
    message: str,
    *,
    display_name: str | None = None,
    tools: list[AppTool] | None = None,
    allow_draft: bool = False,
    llm: LLMClient | None = None,
) -> CompanionReply:
    companion = await store.get_companion(session, tenant_id, companion_id)
    if companion is None:
        raise CompanionNotFound()
    if companion.status != "live" and not (allow_draft and companion.status == "draft"):
        raise CompanionPaused()
    client = llm if llm is not None else get_llm()
    if not client.configured:
        raise CompanionMisconfigured()

    openai_tools = app_tools_to_openai(list(tools or []))
    text_in = message[:MESSAGE_MAX_CHARS]
    now = utcnow()

    semaphore = await _acquire_slot()
    try:
        end_user = await store.get_or_create_end_user(session, tenant_id, external_user_id, display_name)
        conversation = await store.get_or_open_conversation(session, tenant_id, companion, end_user.id, now)
        history = await store.recent_history(session, tenant_id, companion.id, end_user.id, HISTORY_LIMIT)
        kb_context, memory_context = await _gather_context(tenant_id, companion, end_user.id, text_in)
        messages = prompt.build_messages(
            companion,
            conversation.mood,
            kb_context,
            memory_context,
            [{"role": item.role, "content": item.content} for item in history],
            text_in,
        )
        await store.add_message(session, conversation, "user", text_in)
        result = await _chat(client, messages, openai_tools)
    finally:
        semaphore.release()

    return await _conclude(
        session, tenant_id, companion, conversation, messages, result, openai_tools, round_no=1
    )


async def continue_reply(
    session: AsyncSession,
    turn_id: str,
    tenant_id: str,
    results: list[ToolResult],
    *,
    llm: LLMClient | None = None,
) -> CompanionReply:
    now = utcnow()
    await store.sweep_expired_turns(session, tenant_id, now)
    await session.commit()  # keep the sweep even when this call ends in TurnExpired
    turn: CompanionPendingTurn | None = await store.get_pending_turn(session, tenant_id, turn_id, now)
    if turn is None:
        raise TurnExpired()
    companion = await store.get_companion(session, tenant_id, turn.companion_id)
    conversation = await store.get_conversation(session, tenant_id, turn.conversation_id)
    if companion is None or conversation is None:
        raise TurnExpired()
    client = llm if llm is not None else get_llm()
    if not client.configured:
        raise CompanionMisconfigured()

    messages = _apply_results(list(turn.messages), results)
    round_no = turn.round + 1
    tools = list(turn.tools) if round_no < MAX_ROUNDS else []
    await store.delete_pending_turn(session, turn)

    semaphore = await _acquire_slot()
    try:
        result = await _chat(client, messages, tools)
    finally:
        semaphore.release()

    return await _conclude(
        session, tenant_id, companion, conversation, messages, result, tools, round_no=round_no
    )
