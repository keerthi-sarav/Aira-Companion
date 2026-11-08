from dataclasses import dataclass
from typing import Annotated

from fastapi import Header

from app.core.config import get_settings

TENANT_ID_MAX_CHARS = 64  # companions.tenant_id is String(64)
USER_ID_MAX_CHARS = 100  # "owner-test:" + user id must fit companion_end_users.external_user_id String(128)


class Unauthorized(Exception):
    """Dev header auth failure. Rendered as {"error": "unauthorized", "message": ...} with 401."""

    status_code = 401
    code = "unauthorized"

    def __init__(self, message: str = "Missing X-Tenant-Id or X-User-Id header."):
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class TenantContext:
    tenant_id: str
    user_id: str


async def get_tenant(
    x_tenant_id: Annotated[str | None, Header()] = None,
    x_user_id: Annotated[str | None, Header()] = None,
) -> TenantContext:
    """Dev-only seam. Real auth (JWT, settings.manage permission, API keys) replaces this later."""
    if get_settings().APP_ENV != "dev":
        raise Unauthorized("header auth disabled outside dev")
    if not x_tenant_id or not x_tenant_id.strip() or not x_user_id or not x_user_id.strip():
        raise Unauthorized()
    tenant_id = x_tenant_id.strip()
    user_id = x_user_id.strip()
    if len(tenant_id) > TENANT_ID_MAX_CHARS:
        raise Unauthorized(f"X-Tenant-Id must be {TENANT_ID_MAX_CHARS} characters or fewer.")
    if len(user_id) > USER_ID_MAX_CHARS:
        raise Unauthorized(f"X-User-Id must be {USER_ID_MAX_CHARS} characters or fewer.")
    return TenantContext(tenant_id=tenant_id, user_id=user_id)
