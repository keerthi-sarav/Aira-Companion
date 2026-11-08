from typing import Any

from httpx import AsyncClient

BASE = "/api/v1/companions"
TENANT_A = "tenant-astrotamil"
TENANT_B = "tenant-other"
USER = "owner-1"


def hdr(tenant: str = TENANT_A, user: str = USER) -> dict[str, str]:
    return {"X-Tenant-Id": tenant, "X-User-Id": user}


def card(name: str = "Jothidar AI", **extra: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "name": name,
        "role": "Astrologer",
        "backstory": "A family astrologer from Madurai.",
        "speaking_style": "Warm, Tanglish",
        "temperament": "Patient",
        "language": "Tanglish",
        "sample_lines": ["Vanakkam!"],
        "goals": ["Help the user feel clear"],
        "rules": ["Keep answers short"],
        "industry": "astrology",
    }
    body.update(extra)
    return body


async def make_companion(client: AsyncClient, tenant: str = TENANT_A, name: str = "Jothidar AI", **extra: Any) -> dict[str, Any]:
    response = await client.post(BASE, json=card(name, **extra), headers=hdr(tenant))
    assert response.status_code == 201, response.text
    return response.json()


async def set_status(client: AsyncClient, companion_id: str, status: str, tenant: str = TENANT_A) -> None:
    response = await client.patch(f"{BASE}/{companion_id}", json={"status": status}, headers=hdr(tenant))
    assert response.status_code == 200, response.text


async def post_test_chat(client: AsyncClient, companion_id: str, message: str, tenant: str = TENANT_A, **extra: Any) -> Any:
    body = {"message": message, **extra}
    return await client.post(f"{BASE}/{companion_id}/test-chat", json=body, headers=hdr(tenant))
