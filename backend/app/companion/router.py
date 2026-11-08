from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.companion import store
from app.companion.engine import continue_reply, reply
from app.companion.errors import CompanionNotFound
from app.companion.llm import LLMClient, get_llm
from app.companion.schemas import (
    ChatMessageRead,
    CompanionCreate,
    CompanionRead,
    CompanionReply,
    CompanionUpdate,
    ContinueRequest,
    TestChatRequest,
)
from app.core.auth import TenantContext, get_tenant
from app.core.db import get_session

router = APIRouter(prefix="/api/v1/companions", tags=["companions"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
TenantDep = Annotated[TenantContext, Depends(get_tenant)]
LLMDep = Annotated[LLMClient, Depends(get_llm)]

TEST_CHAT_HISTORY_LIMIT = 50


def _owner_test_user(ctx: TenantContext) -> str:
    return f"owner-test:{ctx.user_id}"


async def _require_companion(session: AsyncSession, tenant_id: str, companion_id: str):  # type: ignore[no-untyped-def]
    companion = await store.get_companion(session, tenant_id, companion_id)
    if companion is None:
        raise CompanionNotFound()
    return companion


@router.get("", response_model=list[CompanionRead])
async def list_companions(ctx: TenantDep, session: SessionDep) -> list[CompanionRead]:
    rows = await store.list_companions(session, ctx.tenant_id)
    return [CompanionRead.model_validate(row) for row in rows]


@router.post("", response_model=CompanionRead, status_code=201)
async def create_companion(body: CompanionCreate, ctx: TenantDep, session: SessionDep) -> CompanionRead:
    row = await store.create_companion(session, ctx.tenant_id, body)
    await session.commit()
    return CompanionRead.model_validate(row)


@router.get("/{companion_id}", response_model=CompanionRead)
async def get_companion(companion_id: str, ctx: TenantDep, session: SessionDep) -> CompanionRead:
    row = await _require_companion(session, ctx.tenant_id, companion_id)
    return CompanionRead.model_validate(row)


@router.patch("/{companion_id}", response_model=CompanionRead)
async def update_companion(
    companion_id: str, body: CompanionUpdate, ctx: TenantDep, session: SessionDep
) -> CompanionRead:
    row = await store.update_companion(session, ctx.tenant_id, companion_id, body)
    if row is None:
        raise CompanionNotFound()
    await session.commit()
    return CompanionRead.model_validate(row)


@router.delete("/{companion_id}", status_code=204, response_class=Response)
async def delete_companion(companion_id: str, ctx: TenantDep, session: SessionDep) -> Response:
    deleted = await store.delete_companion(session, ctx.tenant_id, companion_id)
    if not deleted:
        raise CompanionNotFound()
    await session.commit()
    return Response(status_code=204)


@router.post("/{companion_id}/test-chat", response_model=CompanionReply)
async def test_chat(
    companion_id: str, body: TestChatRequest, ctx: TenantDep, session: SessionDep, llm: LLMDep
) -> CompanionReply:
    return await reply(
        session,
        companion_id,
        ctx.tenant_id,
        _owner_test_user(ctx),
        body.message,
        display_name=body.display_name,
        tools=body.tools,
        allow_draft=True,
        llm=llm,
    )


@router.post("/test-chat/continue", response_model=CompanionReply)
async def test_chat_continue(
    body: ContinueRequest, ctx: TenantDep, session: SessionDep, llm: LLMDep
) -> CompanionReply:
    return await continue_reply(session, body.turn_id, ctx.tenant_id, body.results, llm=llm)


@router.get("/{companion_id}/test-chat/history", response_model=list[ChatMessageRead])
async def test_chat_history(companion_id: str, ctx: TenantDep, session: SessionDep) -> list[ChatMessageRead]:
    await _require_companion(session, ctx.tenant_id, companion_id)
    end_user = await store.find_end_user(session, ctx.tenant_id, _owner_test_user(ctx))
    if end_user is None:
        return []
    rows = await store.recent_history(
        session, ctx.tenant_id, companion_id, end_user.id, TEST_CHAT_HISTORY_LIMIT
    )
    return [ChatMessageRead.model_validate(row) for row in rows]


@router.post("/end-users/{external_user_id:path}/forget", status_code=204, response_class=Response)
async def forget_end_user(external_user_id: str, ctx: TenantDep, session: SessionDep) -> Response:
    end_user = await store.find_end_user(session, ctx.tenant_id, external_user_id)
    if end_user is not None:
        await store.forget_end_user(session, ctx.tenant_id, end_user.id)
        await session.commit()
    return Response(status_code=204)
