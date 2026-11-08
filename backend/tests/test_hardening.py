"""Input bounds, header auth limits, and history shape."""

import pytest

from app.core.config import get_settings
from helpers import BASE, TENANT_A, USER, card, hdr, make_companion, post_test_chat


async def test_history_rows_include_message_id(client):
    companion = await make_companion(client)
    cid = companion["id"]
    reply = (await post_test_chat(client, cid, "hello there")).json()

    history = (await client.get(f"{BASE}/{cid}/test-chat/history", headers=hdr())).json()
    assert [m["role"] for m in history] == ["user", "assistant"]
    assert all(isinstance(m["id"], str) and m["id"] for m in history)
    assert history[0]["id"] != history[1]["id"]
    assert history[1]["id"] == reply["message_id"]


async def test_overlong_tenant_header_is_401_not_500(client):
    response = await client.get(BASE, headers={"X-Tenant-Id": "t" * 65, "X-User-Id": USER})
    assert response.status_code == 401
    assert "X-Tenant-Id" in response.json()["message"]

    # Write path too: the tenant id is stored in String(64) columns.
    created = await client.post(BASE, json=card(), headers={"X-Tenant-Id": "t" * 65, "X-User-Id": USER})
    assert created.status_code == 401


async def test_overlong_user_header_is_401_not_500(client):
    response = await client.get(BASE, headers={"X-Tenant-Id": TENANT_A, "X-User-Id": "u" * 101})
    assert response.status_code == 401
    assert "X-User-Id" in response.json()["message"]


async def test_header_lengths_at_the_limit_are_accepted(client):
    response = await client.get(BASE, headers={"X-Tenant-Id": "t" * 64, "X-User-Id": "u" * 100})
    assert response.status_code == 200


async def test_header_auth_refused_outside_dev(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "APP_ENV", "production")
    response = await client.get(BASE, headers=hdr())
    assert response.status_code == 401
    assert response.json()["message"] == "header auth disabled outside dev"


@pytest.mark.parametrize(
    "extra",
    [
        {"fallback_line": "f" * 501},
        {"knowledge_tag_id": "k" * 65},
        {"sample_lines": ["s" * 501]},
        {"goals": ["g" * 501]},
        {"rules": ["r" * 501]},
    ],
)
async def test_create_rejects_values_postgres_columns_would_reject(client, extra):
    response = await client.post(BASE, json=card(**extra), headers=hdr())
    assert response.status_code == 422


async def test_update_rejects_overlong_fallback_tag_and_list_items(client):
    companion = await make_companion(client)
    for body in ({"fallback_line": "f" * 501}, {"knowledge_tag_id": "k" * 65}, {"rules": ["r" * 501]}):
        response = await client.patch(f"{BASE}/{companion['id']}", json=body, headers=hdr())
        assert response.status_code == 422, body
