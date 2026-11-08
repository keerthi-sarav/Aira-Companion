from helpers import BASE, TENANT_A, TENANT_B, hdr, make_companion, post_test_chat


async def test_other_tenant_cannot_see_or_touch_companion(client):
    mine = await make_companion(client, TENANT_A)
    cid = mine["id"]
    other = hdr(TENANT_B)

    assert (await client.get(f"{BASE}/{cid}", headers=other)).status_code == 404
    assert (await client.patch(f"{BASE}/{cid}", json={"role": "hacked"}, headers=other)).status_code == 404
    assert (await client.delete(f"{BASE}/{cid}", headers=other)).status_code == 404
    assert (await client.get(f"{BASE}/{cid}/test-chat/history", headers=other)).status_code == 404
    assert (await post_test_chat(client, cid, "hello", tenant=TENANT_B)).status_code == 404


async def test_other_tenant_list_is_empty_and_names_do_not_collide(client):
    await make_companion(client, TENANT_A, name="Jothidar AI")
    assert (await client.get(BASE, headers=hdr(TENANT_B))).json() == []

    same_name = await make_companion(client, TENANT_B, name="Jothidar AI")
    assert same_name["tenant_id"] == TENANT_B

    still_mine = await client.get(BASE, headers=hdr(TENANT_A))
    assert [row["tenant_id"] for row in still_mine.json()] == [TENANT_A]


async def test_tenant_a_patch_does_not_leak_into_tenant_b(client):
    a = await make_companion(client, TENANT_A, name="Shared name")
    b = await make_companion(client, TENANT_B, name="Shared name")
    await client.patch(f"{BASE}/{a['id']}", json={"role": "changed by A"}, headers=hdr(TENANT_A))
    b_after = (await client.get(f"{BASE}/{b['id']}", headers=hdr(TENANT_B))).json()
    assert b_after["role"] != "changed by A"
