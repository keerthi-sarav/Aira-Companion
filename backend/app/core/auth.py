from dataclasses import dataclass
from typing import Annotated

from fastapi import Header


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
    if not x_tenant_id or not x_tenant_id.strip() or not x_user_id or not x_user_id.strip():
        raise Unauthorized()
    return TenantContext(tenant_id=x_tenant_id.strip(), user_id=x_user_id.strip())
