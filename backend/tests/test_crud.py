from helpers import BASE, TENANT_A, card, hdr, make_companion


async def test_create_returns_201_with_defaults(client):
    created = await make_companion(client)
    assert created["status"] == "draft"
    assert created["default_mood"] == "calm"
    assert created["privacy_mode"] == "B"
    assert created["tenant_id"] == TENANT_A
    assert created["fallback_line"].startswith("Sorry, I can't answer right now")
    assert created["sample_lines"] == ["Vanakkam!"]
    assert created["created_at"] and created["updated_at"]


async def test_list_get_patch_delete_roundtrip(client):
    created = await make_companion(client)
    cid = created["id"]

    listed = await client.get(BASE, headers=hdr())
    assert listed.status_code == 200
    assert [row["id"] for row in listed.json()] == [cid]

    fetched = await client.get(f"{BASE}/{cid}", headers=hdr())
    assert fetched.status_code == 200 and fetched.json()["name"] == "Jothidar AI"

    patched = await client.patch(f"{BASE}/{cid}", json={"role": "Senior astrologer", "status": "live"}, headers=hdr())
    assert patched.status_code == 200
    assert patched.json()["role"] == "Senior astrologer"
    assert patched.json()["status"] == "live"
    assert patched.json()["name"] == "Jothidar AI"  # unset fields untouched

    deleted = await client.delete(f"{BASE}/{cid}", headers=hdr())
    assert deleted.status_code == 204

    gone = await client.get(f"{BASE}/{cid}", headers=hdr())
    assert gone.status_code == 404
    assert gone.json()["error"] == "companion_not_found"


async def test_duplicate_name_is_409_for_same_tenant(client):
    await make_companion(client, name="Vastu Guru")
    response = await client.post(BASE, json=card("Vastu Guru"), headers=hdr())
    assert response.status_code == 409
    assert response.json()["error"] == "duplicate_name"
    assert "message" in response.json()


async def test_rename_to_existing_name_is_409(client):
    await make_companion(client, name="Vastu Guru")
    other = await make_companion(client, name="Jothidar AI")
    response = await client.patch(f"{BASE}/{other['id']}", json={"name": "Vastu Guru"}, headers=hdr())
    assert response.status_code == 409
    assert response.json()["error"] == "duplicate_name"


async def test_missing_headers_is_401(client):
    response = await client.get(BASE)
    assert response.status_code == 401
    assert response.json()["error"] == "unauthorized"

    response = await client.get(BASE, headers={"X-Tenant-Id": TENANT_A})
    assert response.status_code == 401


async def test_validation_limits_are_enforced(client):
    too_many_goals = card("Limits", goals=["a", "b", "c", "d", "e", "f"])
    response = await client.post(BASE, json=too_many_goals, headers=hdr())
    assert response.status_code == 422

    too_many_tools = {
        "message": "hi",
        "tools": [{"name": f"tool_{i}", "description": "d", "parameters": {}} for i in range(9)],
    }
    created = await make_companion(client)
    response = await client.post(f"{BASE}/{created['id']}/test-chat", json=too_many_tools, headers=hdr())
    assert response.status_code == 422


async def test_bad_tool_name_is_422(client):
    created = await make_companion(client)
    body = {"message": "hi", "tools": [{"name": "Get-Chart!", "description": "d", "parameters": {}}]}
    response = await client.post(f"{BASE}/{created['id']}/test-chat", json=body, headers=hdr())
    assert response.status_code == 422


async def test_oversized_tool_parameters_is_422(client):
    created = await make_companion(client)
    big = {"type": "object", "properties": {"x": {"description": "y" * 5000}}}
    body = {"message": "hi", "tools": [{"name": "get_chart", "description": "d", "parameters": big}]}
    response = await client.post(f"{BASE}/{created['id']}/test-chat", json=body, headers=hdr())
    assert response.status_code == 422
