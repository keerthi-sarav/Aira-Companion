"""LLM client seam. OpenAI-format messages and tools throughout."""

import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from app.companion.schemas import AppTool, ToolCall
from app.core.config import get_settings


@dataclass
class LLMResult:
    text: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: dict[str, Any] | None = None


class LLMClient(Protocol):
    configured: bool

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | None = None,
        max_tokens: int = 700,
        temperature: float = 0.5,
        purpose: str = "companion_reply",
    ) -> LLMResult: ...


def app_tools_to_openai(tools: list[AppTool]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {"name": tool.name, "description": tool.description, "parameters": tool.parameters},
        }
        for tool in tools
    ]


def _parse_arguments(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


class OpenAICompatLLM:
    """Any OpenAI-compatible /chat/completions endpoint (Groq, Gemini-OpenAI, Sarvam...)."""

    def __init__(
        self,
        *,
        base_url: str | None,
        api_key: str | None,
        model: str | None,
        timeout: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self._base_url = (base_url or "").rstrip("/")
        self._api_key = (api_key or "").strip()
        self._model = (model or "").strip()
        self._timeout = timeout
        self._transport = transport

    @property
    def configured(self) -> bool:
        return bool(self._api_key and self._model)

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | None = None,
        max_tokens: int = 700,
        temperature: float = 0.5,
        purpose: str = "companion_reply",
    ) -> LLMResult:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = tools
            if tool_choice:
                payload["tool_choice"] = tool_choice  # "none" = tools are visible but must not be called
        async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
            response = await client.post(
                f"{self._base_url}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
        response.raise_for_status()
        data = response.json()
        message = data["choices"][0]["message"]
        tool_calls = []
        for call in message.get("tool_calls") or []:
            function = call.get("function") or {}
            tool_calls.append(
                ToolCall(
                    id=call.get("id") or f"call_{uuid.uuid4().hex[:12]}",
                    name=function.get("name", ""),
                    args=_parse_arguments(function.get("arguments")),
                )
            )
        return LLMResult(text=message.get("content"), tool_calls=tool_calls, usage=data.get("usage"))


class FakeLLM:
    """Dev and test client. Echoes the last user message with a warm mood.

    With tools offered and "chart" in the user message, it asks for the first tool once.
    After a tool result has been appended, it answers with text, so the pause flow terminates.
    """

    configured = True

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | None = None,
        max_tokens: int = 700,
        temperature: float = 0.5,
        purpose: str = "companion_reply",
    ) -> LLMResult:
        self.calls.append({"messages": list(messages), "tools": tools, "tool_choice": tool_choice})
        last_user_index = max((i for i, m in enumerate(messages) if m["role"] == "user"), default=-1)
        last_user = messages[last_user_index]["content"] if last_user_index >= 0 else ""
        tool_result_seen = any(m["role"] == "tool" for m in messages[last_user_index + 1:])
        if tools and tool_choice != "none" and "chart" in last_user.lower() and not tool_result_seen:
            name = tools[0]["function"]["name"]
            call = ToolCall(id=f"call_{uuid.uuid4().hex[:12]}", name=name, args={})
            return LLMResult(text=None, tool_calls=[call])
        return LLMResult(text=f"[mood: warm] (echo) {last_user}")


def get_llm() -> LLMClient:
    """FastAPI dependency. Tests override it with dependency_overrides."""
    settings = get_settings()
    if settings.LLM_PROVIDER == "openai_compat":
        return OpenAICompatLLM(
            base_url=settings.LLM_BASE_URL,
            api_key=settings.LLM_API_KEY,
            model=settings.LLM_MODEL,
        )
    return FakeLLM()
