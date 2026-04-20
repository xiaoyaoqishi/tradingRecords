import uuid


def _create_account(client, name):
    r = client.post(
        "/api/ledger/accounts",
        json={"name": name, "account_type": "cash", "currency": "CNY", "initial_balance": 0},
    )
    assert r.status_code == 200
    return r.json()["id"]


def test_ledger_rules_reapply_updates_only_when_changed(admin_login):
    client = admin_login
    account_id = _create_account(client, "rule-reapply-a1")

    rule = client.post(
        "/api/ledger/rules",
        json={
            "name": "统一商户名",
            "priority": 10,
            "is_active": True,
            "match_json": {"merchant_contains": "star"},
            "action_json": {"set_merchant": "Starbucks"},
        },
    )
    assert rule.status_code == 200

    tx = client.post(
        "/api/ledger/transactions?apply_rules=false",
        json={
            "occurred_at": "2026-04-20T11:00:00",
            "account_id": account_id,
            "direction": "income",
            "transaction_type": "income",
            "amount": 30,
            "currency": "CNY",
            "merchant": "Star Bucks",
        },
    )
    assert tx.status_code == 200
    tx_id = tx.json()["id"]

    first = client.post("/api/ledger/rules/reapply", json={"transaction_ids": [tx_id]})
    assert first.status_code == 200
    assert first.json()["scanned_count"] == 1
    assert first.json()["updated_count"] == 1

    second = client.post("/api/ledger/rules/reapply", json={"transaction_ids": [tx_id]})
    assert second.status_code == 200
    assert second.json()["updated_count"] == 0
    assert second.json()["skipped_count"] == 1


def test_ledger_rules_reapply_owner_isolated(admin_login):
    client = admin_login

    admin_account_id = _create_account(client, "rule-reapply-admin")
    admin_rule = client.post(
        "/api/ledger/rules",
        json={
            "name": "admin-merchant",
            "priority": 10,
            "is_active": True,
            "match_json": {"merchant_contains": "book"},
            "action_json": {"set_merchant": "ADMIN_BOOK"},
        },
    )
    assert admin_rule.status_code == 200

    admin_tx = client.post(
        "/api/ledger/transactions?apply_rules=false",
        json={
            "occurred_at": "2026-04-20T09:00:00",
            "account_id": admin_account_id,
            "direction": "income",
            "transaction_type": "income",
            "amount": 50,
            "currency": "CNY",
            "merchant": "book-store",
        },
    )
    assert admin_tx.status_code == 200
    admin_tx_id = admin_tx.json()["id"]

    username = f"rule_reapply_user_{uuid.uuid4().hex[:8]}"
    create_user = client.post("/api/admin/users", json={"username": username, "password": "u123456"})
    assert create_user.status_code == 200

    client.post("/api/auth/logout")
    login_user = client.post("/api/auth/login", json={"username": username, "password": "u123456"})
    assert login_user.status_code == 200

    user_account_id = _create_account(client, "rule-reapply-user")
    user_rule = client.post(
        "/api/ledger/rules",
        json={
            "name": "user-merchant",
            "priority": 10,
            "is_active": True,
            "match_json": {"merchant_contains": "book"},
            "action_json": {"set_merchant": "USER_BOOK"},
        },
    )
    assert user_rule.status_code == 200

    user_tx = client.post(
        "/api/ledger/transactions?apply_rules=false",
        json={
            "occurred_at": "2026-04-20T10:00:00",
            "account_id": user_account_id,
            "direction": "income",
            "transaction_type": "income",
            "amount": 66,
            "currency": "CNY",
            "merchant": "book-store",
        },
    )
    assert user_tx.status_code == 200

    # 用户重应用时即便传入 admin 的 transaction_id，也不应扫描/更新到 admin 记录
    user_reapply = client.post(
        "/api/ledger/rules/reapply",
        json={"transaction_ids": [admin_tx_id, user_tx.json()["id"]]},
    )
    assert user_reapply.status_code == 200
    payload = user_reapply.json()
    assert payload["scanned_count"] == 1
    assert payload["updated_count"] == 1

    client.post("/api/auth/logout")
    admin_login_resp = client.post("/api/auth/login", json={"username": "xiaoyao", "password": "admin123"})
    assert admin_login_resp.status_code == 200

    admin_tx_after = client.get(f"/api/ledger/transactions/{admin_tx_id}")
    assert admin_tx_after.status_code == 200
    assert admin_tx_after.json()["merchant"] == "book-store"
