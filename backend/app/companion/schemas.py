import json
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Mood = Literal["calm", "warm", "happy", "concerned", "encouraging", "serious"]
Status = Literal["draft", "live", "paused"]
Industry = Literal["astrology", "general"]
PrivacyMode = Literal["A", "B"]

DEFAULT_FALLBACK_LINE = "Sorry, I can't answer right now. Please try again in a moment."
MESSAGE_MAX_CHARS = 8000
TOOL_OUTPUT_MAX_CHARS = 4000
TOOL_PARAMETERS_MAX_BYTES = 4096


class CharacterCard(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    role: str = Field(default="", max_length=200)
    backstory: str = Field(default="", max_length=2000)
    speaking_style: str = Field(default="", max_length=1000)
    temperament: str = Field(default="", max_length=200)
    language: str = Field(default="English", max_length=40)
    sample_lines: list[str] = Field(default_factory=list, max_length=10)
    goals: list[str] = Field(default_factory=list, max_length=5)
    rules: list[str] = Field(default_factory=list, max_length=30)


class CompanionCreate(CharacterCard):
    industry: Industry = "general"
    default_mood: Mood = "calm"
    knowledge_tag_id: str | None = None
    privacy_mode: PrivacyMode = "B"
    fallback_line: str = DEFAULT_FALLBACK_LINE


class CompanionUpdate(BaseModel):
    """All fields optional. Fields left unset are not touched; explicit null is ignored for non-nullable fields."""

    name: str | None = Field(default=None, min_length=1, max_length=80)
    role: str | None = Field(default=None, max_length=200)
    backstory: str | None = Field(default=None, max_length=2000)
    speaking_style: str | None = Field(default=None, max_length=1000)
    temperament: str | None = Field(default=None, max_length=200)
    language: str | None = Field(default=None, max_length=40)
    sample_lines: list[str] | None = Field(default=None, max_length=10)
    goals: list[str] | None = Field(default=None, max_length=5)
    rules: list[str] | None = Field(default=None, max_length=30)
    industry: Industry | None = None
    default_mood: Mood | None = None
    knowledge_tag_id: str | None = None
    privacy_mode: PrivacyMode | None = None
    fallback_line: str | None = None
    status: Status | None = None


class CompanionRead(CompanionCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    status: Status
    created_at: datetime
    updated_at: datetime


class AppTool(BaseModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]{0,39}$")
    description: str = Field(max_length=500)
    parameters: dict[str, Any]

    @field_validator("parameters")
    @classmethod
    def _parameters_size(cls, value: dict[str, Any]) -> dict[str, Any]:
        size = len(json.dumps(value, ensure_ascii=False).encode("utf-8"))
        if size > TOOL_PARAMETERS_MAX_BYTES:
            raise ValueError(f"tool parameters must serialize to {TOOL_PARAMETERS_MAX_BYTES} bytes or less")
        return value


class TestChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=MESSAGE_MAX_CHARS)
    display_name: str | None = None
    tools: list[AppTool] = Field(default_factory=list, max_length=8)


class ToolCall(BaseModel):
    id: str
    name: str
    args: dict[str, Any]


class ToolResult(BaseModel):
    id: str
    output: Any


class ContinueRequest(BaseModel):
    turn_id: str
    results: list[ToolResult]


class CompanionReply(BaseModel):
    status: Literal["done", "tool_call"]
    text: str | None = None
    mood: Mood | None = None
    conversation_id: str
    message_id: str | None = None
    turn_id: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)


class ChatMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    role: Literal["user", "assistant"]
    content: str
    mood: Mood | None = None
    tool_calls: list[dict[str, Any]] | None = None
    created_at: datetime
