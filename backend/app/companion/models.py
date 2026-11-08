import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from app.core.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid.uuid4())


class UTCDateTime(TypeDecorator):
    """Timezone-aware UTC datetimes. SQLite drops tzinfo on read, so we restore it."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class Companion(Base):
    __tablename__ = "companions"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_companions_tenant_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(16), default="draft")
    industry: Mapped[str] = mapped_column(String(16), default="general")
    language: Mapped[str] = mapped_column(String(40), default="English")
    role: Mapped[str] = mapped_column(String(200), default="")
    backstory: Mapped[str] = mapped_column(String(2000), default="")
    speaking_style: Mapped[str] = mapped_column(String(1000), default="")
    temperament: Mapped[str] = mapped_column(String(200), default="")
    sample_lines: Mapped[list[str]] = mapped_column(JSON, default=lambda: [])
    goals: Mapped[list[str]] = mapped_column(JSON, default=lambda: [])
    rules: Mapped[list[str]] = mapped_column(JSON, default=lambda: [])
    default_mood: Mapped[str] = mapped_column(String(16), default="calm")
    knowledge_tag_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    privacy_mode: Mapped[str] = mapped_column(String(1), default="B")
    fallback_line: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class CompanionEndUser(Base):
    __tablename__ = "companion_end_users"
    __table_args__ = (UniqueConstraint("tenant_id", "external_user_id", name="uq_end_users_tenant_external"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    external_user_id: Mapped[str] = mapped_column(String(128))
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    forgotten_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class CompanionConversation(Base):
    __tablename__ = "companion_conversations"
    __table_args__ = (Index("ix_conversations_lookup", "tenant_id", "companion_id", "end_user_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    companion_id: Mapped[str] = mapped_column(String(36), ForeignKey("companions.id"), index=True)
    end_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("companion_end_users.id"), index=True)
    mood: Mapped[str] = mapped_column(String(16), default="calm")
    last_message_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class CompanionMessage(Base):
    __tablename__ = "companion_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("companion_conversations.id"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    mood: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # Tool names and args only. Tool OUTPUT is never stored here.
    tool_calls: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class CompanionPendingTurn(Base):
    __tablename__ = "companion_pending_turns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    companion_id: Mapped[str] = mapped_column(String(36), ForeignKey("companions.id"), index=True)
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("companion_conversations.id"), index=True)
    # OpenAI-format message list so far. Tool outputs live here only while the turn is in flight.
    messages: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=lambda: [])
    tools: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=lambda: [])
    round: Mapped[int] = mapped_column("round", Integer, default=1)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
