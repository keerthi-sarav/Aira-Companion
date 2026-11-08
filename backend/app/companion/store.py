"""All DB reads and writes for the companion module. Every query filters by tenant_id.

Functions flush but do not commit. The caller (engine or router) commits.
"""

from datetime import timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.companion import memory
from app.companion.errors import DuplicateName
from app.companion.models import (
    Companion,
    CompanionConversation,
    CompanionEndUser,
    CompanionMessage,
    CompanionPendingTurn,
    new_id,
    utcnow,
)
from app.companion.schemas import CompanionCreate, CompanionUpdate

CONVERSATION_ROLLOVER = timedelta(hours=24)
PENDING_TURN_TTL = timedelta(minutes=2)
NULLABLE_COMPANION_FIELDS = {"knowledge_tag_id"}
DISPLAY_NAME_MAX = 120


# ---------- companions ----------

async def get_companion(session: AsyncSession, tenant_id: str, companion_id: str) -> Companion | None:
    result = await session.execute(
        select(Companion).where(Companion.id == companion_id, Companion.tenant_id == tenant_id)
    )
    return result.scalar_one_or_none()


async def list_companions(session: AsyncSession, tenant_id: str) -> list[Companion]:
    result = await session.execute(
        select(Companion).where(Companion.tenant_id == tenant_id).order_by(Companion.created_at, Companion.name)
    )
    return list(result.scalars().all())


async def _name_taken(session: AsyncSession, tenant_id: str, name: str, exclude_id: str | None = None) -> bool:
    query = select(Companion.id).where(Companion.tenant_id == tenant_id, Companion.name == name)
    if exclude_id is not None:
        query = query.where(Companion.id != exclude_id)
    return (await session.execute(query)).first() is not None


async def create_companion(session: AsyncSession, tenant_id: str, data: CompanionCreate) -> Companion:
    if await _name_taken(session, tenant_id, data.name):
        raise DuplicateName()
    now = utcnow()
    row = Companion(tenant_id=tenant_id, created_at=now, updated_at=now, **data.model_dump())
    session.add(row)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise DuplicateName() from exc
    return row


async def update_companion(
    session: AsyncSession, tenant_id: str, companion_id: str, data: CompanionUpdate
) -> Companion | None:
    row = await get_companion(session, tenant_id, companion_id)
    if row is None:
        return None
    changes = data.model_dump(exclude_unset=True)
    for key, value in changes.items():
        if value is None and key not in NULLABLE_COMPANION_FIELDS:
            continue
        if key == "name" and value != row.name and await _name_taken(session, tenant_id, value, exclude_id=row.id):
            raise DuplicateName()
        setattr(row, key, value)
    row.updated_at = utcnow()
    try:
        await session.flush()
    except IntegrityError as exc:
        raise DuplicateName() from exc
    return row


async def delete_companion(session: AsyncSession, tenant_id: str, companion_id: str) -> bool:
    row = await get_companion(session, tenant_id, companion_id)
    if row is None:
        return False
    conversation_ids = select(CompanionConversation.id).where(
        CompanionConversation.tenant_id == tenant_id, CompanionConversation.companion_id == companion_id
    )
    await session.execute(
        delete(CompanionPendingTurn).where(
            CompanionPendingTurn.tenant_id == tenant_id, CompanionPendingTurn.companion_id == companion_id
        )
    )
    await session.execute(
        delete(CompanionMessage).where(
            CompanionMessage.tenant_id == tenant_id, CompanionMessage.conversation_id.in_(conversation_ids)
        )
    )
    await session.execute(
        delete(CompanionConversation).where(
            CompanionConversation.tenant_id == tenant_id, CompanionConversation.companion_id == companion_id
        )
    )
    await session.delete(row)
    await session.flush()
    return True


# ---------- end users ----------

async def find_end_user(session: AsyncSession, tenant_id: str, external_user_id: str) -> CompanionEndUser | None:
    result = await session.execute(
        select(CompanionEndUser).where(
            CompanionEndUser.tenant_id == tenant_id, CompanionEndUser.external_user_id == external_user_id
        )
    )
    return result.scalar_one_or_none()


def _dialect_insert(session: AsyncSession) -> Any:
    bind = session.bind
    if bind is not None and bind.dialect.name == "postgresql":
        return postgresql.insert
    return sqlite.insert


async def get_or_create_end_user(
    session: AsyncSession, tenant_id: str, external_user_id: str, display_name: str | None
) -> CompanionEndUser:
    user = await find_end_user(session, tenant_id, external_user_id)
    if user is None:
        # Insert-or-ignore keeps two concurrent first messages from colliding on the unique key.
        statement = _dialect_insert(session)(CompanionEndUser).values(
            id=new_id(),
            tenant_id=tenant_id,
            external_user_id=external_user_id,
            display_name=None,
            forgotten_at=None,
            created_at=utcnow(),
        )
        await session.execute(statement.on_conflict_do_nothing(index_elements=["tenant_id", "external_user_id"]))
        user = await find_end_user(session, tenant_id, external_user_id)
        if user is None:  # pragma: no cover - defensive
            raise RuntimeError("end user row missing after insert")
    if display_name and user.display_name != display_name[:DISPLAY_NAME_MAX]:
        user.display_name = display_name[:DISPLAY_NAME_MAX]
    return user


# ---------- conversations and messages ----------

async def get_or_open_conversation(
    session: AsyncSession, tenant_id: str, companion: Companion, end_user_id: str, now: Any
) -> CompanionConversation:
    """One open conversation per (companion, end user). New after 24 h of silence, mood carried over."""
    latest = (
        await session.execute(
            select(CompanionConversation)
            .where(
                CompanionConversation.tenant_id == tenant_id,
                CompanionConversation.companion_id == companion.id,
                CompanionConversation.end_user_id == end_user_id,
            )
            .order_by(CompanionConversation.last_message_at.desc())
            .limit(1)
        )
    ).scalars().first()
    if latest is not None and now - latest.last_message_at < CONVERSATION_ROLLOVER:
        return latest
    mood = latest.mood if latest is not None else companion.default_mood
    conversation = CompanionConversation(
        tenant_id=tenant_id,
        companion_id=companion.id,
        end_user_id=end_user_id,
        mood=mood,
        last_message_at=now,
        created_at=now,
    )
    session.add(conversation)
    await session.flush()
    return conversation


async def get_conversation(session: AsyncSession, tenant_id: str, conversation_id: str) -> CompanionConversation | None:
    result = await session.execute(
        select(CompanionConversation).where(
            CompanionConversation.id == conversation_id, CompanionConversation.tenant_id == tenant_id
        )
    )
    return result.scalar_one_or_none()


async def recent_history(
    session: AsyncSession, tenant_id: str, companion_id: str, end_user_id: str, limit: int
) -> list[CompanionMessage]:
    """Last `limit` messages for this companion AND this end user, oldest first."""
    result = await session.execute(
        select(CompanionMessage)
        .join(CompanionConversation, CompanionMessage.conversation_id == CompanionConversation.id)
        .where(
            CompanionMessage.tenant_id == tenant_id,
            CompanionConversation.tenant_id == tenant_id,
            CompanionConversation.companion_id == companion_id,
            CompanionConversation.end_user_id == end_user_id,
        )
        .order_by(CompanionMessage.created_at.desc(), CompanionMessage.id.desc())
        .limit(limit)
    )
    return list(reversed(result.scalars().all()))


async def add_message(
    session: AsyncSession,
    conversation: CompanionConversation,
    role: str,
    content: str,
    *,
    mood: str | None = None,
    tool_calls: list[dict[str, Any]] | None = None,
) -> CompanionMessage:
    now = utcnow()
    message = CompanionMessage(
        tenant_id=conversation.tenant_id,
        conversation_id=conversation.id,
        role=role,
        content=content,
        mood=mood,
        tool_calls=tool_calls,
        created_at=now,
    )
    session.add(message)
    conversation.last_message_at = now
    await session.flush()
    return message


# ---------- pending tool turns ----------

async def sweep_expired_turns(session: AsyncSession, tenant_id: str, now: Any) -> None:
    await session.execute(
        delete(CompanionPendingTurn).where(
            CompanionPendingTurn.tenant_id == tenant_id, CompanionPendingTurn.expires_at <= now
        )
    )


async def create_pending_turn(
    session: AsyncSession,
    tenant_id: str,
    companion_id: str,
    conversation_id: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    round_no: int,
) -> CompanionPendingTurn:
    now = utcnow()
    await sweep_expired_turns(session, tenant_id, now)
    turn = CompanionPendingTurn(
        id=new_id(),
        tenant_id=tenant_id,
        companion_id=companion_id,
        conversation_id=conversation_id,
        messages=messages,
        tools=tools,
        round=round_no,
        expires_at=now + PENDING_TURN_TTL,
        created_at=now,
    )
    session.add(turn)
    await session.flush()
    return turn


async def get_pending_turn(
    session: AsyncSession, tenant_id: str, turn_id: str, now: Any
) -> CompanionPendingTurn | None:
    result = await session.execute(
        select(CompanionPendingTurn).where(
            CompanionPendingTurn.id == turn_id, CompanionPendingTurn.tenant_id == tenant_id
        )
    )
    turn = result.scalar_one_or_none()
    if turn is None or turn.expires_at <= now:
        return None
    return turn


async def delete_pending_turn(session: AsyncSession, turn: CompanionPendingTurn) -> None:
    await session.delete(turn)
    await session.flush()


# ---------- forget me ----------

async def forget_end_user(session: AsyncSession, tenant_id: str, end_user_id: str) -> None:
    """Hard-delete this person's chats, conversations and pending turns across ALL companions of the tenant."""
    conversation_ids = select(CompanionConversation.id).where(
        CompanionConversation.tenant_id == tenant_id, CompanionConversation.end_user_id == end_user_id
    )
    await session.execute(
        delete(CompanionPendingTurn).where(
            CompanionPendingTurn.tenant_id == tenant_id,
            CompanionPendingTurn.conversation_id.in_(conversation_ids),
        )
    )
    await session.execute(
        delete(CompanionMessage).where(
            CompanionMessage.tenant_id == tenant_id, CompanionMessage.conversation_id.in_(conversation_ids)
        )
    )
    await session.execute(
        delete(CompanionConversation).where(
            CompanionConversation.tenant_id == tenant_id, CompanionConversation.end_user_id == end_user_id
        )
    )
    result = await session.execute(
        select(CompanionEndUser).where(CompanionEndUser.id == end_user_id, CompanionEndUser.tenant_id == tenant_id)
    )
    user = result.scalar_one_or_none()
    if user is not None:
        user.display_name = None
        user.forgotten_at = utcnow()
    await session.flush()
    await memory.memory_provider.forget(end_user_id)
