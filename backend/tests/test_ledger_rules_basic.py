import uuid


def _create_account(client, name):
    r = client.post(
        "/api/ledger/accounts",
        json={"name": name, "account_type": "cash", "currency": "CNY", "initial_balance": 0},
    )
    assert r.status_code == 200
    return r.json()["id"]


def _create_category(client, name):
    r = client.post(
        "/api/ledger/categories",
        json={"name": name, "category_type": "expense", "sort_order": 1, "is_active": True},
    )
    assert r.status_code == 200
    return r.json()["id"]


def test_ledger_rules_crud(admin_login):
    client = admin_login

    create = client.post(
        "/api/ledger/rules",
        json={
            "name": "coffee-rule",
            "priority": 100,
            "is_active": True,
            "match_json": {"merchant_contains": "coffee"},
            "action_json": {"set_merchant": "Coffee Shop"},
        },
    )
    assert create.status_code == 200
    rule_id = create.json()["id"]

    listed = client.get("/api/ledger/rules")
    assert listed.status_code == 200
    assert any(x["id"] == rule_id for x in listed.json()["items"])

    updated = client.put(
        f"/api/ledger/rules/{rule_id}",
        json={"priority": 12, "is_active": False},
    )
    assert updated.status_code == 200
    assert updated.json()["priority"] == 12
    assert updated.json()["is_active"] is False

    deleted = client.delete(f"/api/ledger/rules/{rule_id}")
    assert deleted.status_code == 200
    after = client.get("/api/ledger/rules")
    ids = [x["id"] for x in after.json()["items"]]
    assert rule_id not in ids


def test_ledger_rules_match_and_priority_chain(admin_login):
    client = admin_login
    account_id = _create_account(client, "rule-tx-a1")

    r1 = client.post(
        "/api/ledger/rules",
        json={
            "name": "set-merchant-a",
            "priority": 10,
            "is_active": True,
            "match_json": {"description_contains": "午餐"},
            "action_json": {"set_merchant": "餐饮A"},
        },
    )
    assert r1.status_code == 200

    r2 = client.post(
        "/api/ledger/rules",
        json={
            "name": "set-merchant-b",
            "priority": 20,
            "is_active": True,
            "match_json": {"description_contains": "午餐"},
            "action_json": {"set_merchant": "餐饮B"},
        },
    )
    assert r2.status_code == 200

    created = client.post(
        "/api/ledger/transactions",
        json={
            "occurred_at": "2026-04-20T12:30:00",
            "account_id": account_id,
            "direction": "income",
            "transaction_type": "income",
            "amount": 10,
            "currency": "CNY",
            "description": "午餐退款",
            "merchant": "原始商户",
        },
    )
    assert created.status_code == 200
    payload = created.json()
    assert payload["merchant"] == "餐饮B"
    assert payload["matched_rules"]["matched_rule_names"] == ["set-merchant-a", "set-merchant-b"]


def test_ledger_rule_auto_sets_category_for_expense(admin_login):
    client = admin_login
    account_id = _create_account(client, "rule-tx-a2")
    category_id = _create_category(client, "rule-expense-c1")

    create_rule = client.post(
        "/api/ledger/rules",
        json={
            "name": "餐饮自动分类",
            "priority": 5,
            "is_active": True,
            "match_json": {"merchant_contains": ["coffee", "cafe"], "transaction_type": "expense"},
            "action_json": {"set_category_id": category_id},
        },
    )
    assert create_rule.status_code == 200

    created = client.post(
        "/api/ledger/transactions",
        json={
            "occurred_at": "2026-04-20T13:00:00",
            "account_id": account_id,
            "direction": "expense",
            "transaction_type": "expense",
            "amount": 36,
            "currency": "CNY",
            "merchant": "Coffee House",
            "description": "latte",
        },
    )
    assert created.status_code == 200
    payload = created.json()
    assert payload["category_id"] == category_id
    assert payload["matched_rules"]["matched_rule_names"] == ["餐饮自动分类"]


def test_ledger_rules_owner_isolated(admin_login):
    client = admin_login

    admin_rule = client.post(
        "/api/ledger/rules",
        json={
            "name": "admin-only-rule",
            "priority": 1,
            "is_active": True,
            "match_json": {"merchant_contains": "admin"},
            "action_json": {"set_merchant": "ADMIN"},
        },
    )
    assert admin_rule.status_code == 200

    username = f"ledger_rule_user_{uuid.uuid4().hex[:8]}"
    create_user = client.post("/api/admin/users", json={"username": username, "password": "u123456"})
    assert create_user.status_code == 200

    client.post("/api/auth/logout")
    user_login = client.post("/api/auth/login", json={"username": username, "password": "u123456"})
    assert user_login.status_code == 200

    listed = client.get("/api/ledger/rules")
    assert listed.status_code == 200
    names = [x["name"] for x in listed.json()["items"]]
    assert "admin-only-rule" not in names
