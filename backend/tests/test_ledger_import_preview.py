import json
import uuid


def _create_account(client, name):
    r = client.post(
        "/api/ledger/accounts",
        json={"name": name, "account_type": "cash", "currency": "CNY", "initial_balance": 0},
    )
    assert r.status_code == 200
    return r.json()["id"]


def _create_category(client, name="food"):
    r = client.post(
        "/api/ledger/categories",
        json={"name": name, "category_type": "expense", "sort_order": 1, "is_active": True},
    )
    assert r.status_code == 200
    return r.json()["id"]


def _preview(client, csv_text, mapping, **extra_data):
    data = {
        "delimiter": ",",
        "encoding": "utf-8",
        "has_header": "true",
        "mapping_json": json.dumps(mapping, ensure_ascii=False),
        "preview_limit": "100",
    }
    data.update(extra_data)
    return client.post(
        "/api/ledger/import/preview",
        data=data,
        files={"file": ("sample.csv", csv_text.encode("utf-8"), "text/csv")},
    )


def test_ledger_import_preview_success(admin_login):
    client = admin_login
    _create_account(client, "import-preview-a1")
    _create_category(client, "import-preview-c1")

    csv_text = "date,amount,type,direction,account,category,merchant\n2026-04-20 09:00:00,120.5,expense,expense,import-preview-a1,import-preview-c1,coffee\n"
    mapping = {
        "occurred_at": "date",
        "amount": "amount",
        "transaction_type": "type",
        "direction": "direction",
        "account_name": "account",
        "category_name": "category",
        "merchant": "merchant",
    }

    resp = _preview(client, csv_text, mapping)
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["stats"]["total_rows"] == 1
    assert payload["stats"]["valid_rows"] == 1
    assert payload["stats"]["invalid_rows"] == 0


def test_ledger_import_preview_invalid_rows(admin_login):
    client = admin_login
    _create_account(client, "import-preview-a2")

    csv_text = "date,amount,type,direction,account\n2026-04-20 09:00:00,abc,expense,expense,import-preview-a2\n"
    mapping = {
        "occurred_at": "date",
        "amount": "amount",
        "transaction_type": "type",
        "direction": "direction",
        "account_name": "account",
    }

    resp = _preview(client, csv_text, mapping)
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["stats"]["invalid_rows"] == 1
    assert payload["preview_rows"][0]["status"] == "invalid"


def test_ledger_import_preview_duplicate_rows(admin_login):
    client = admin_login
    account_id = _create_account(client, "import-preview-a3")

    existed = client.post(
        "/api/ledger/transactions",
        json={
            "occurred_at": "2026-04-20T10:00:00",
            "account_id": account_id,
            "direction": "income",
            "transaction_type": "income",
            "amount": 88,
            "currency": "CNY",
            "merchant": "dup-shop",
            "external_ref": "dup-001",
        },
    )
    assert existed.status_code == 200

    csv_text = "date,amount,type,direction,account,merchant,external_ref\n2026-04-20 10:00:00,88,income,income,import-preview-a3,dup-shop,dup-001\n"
    mapping = {
        "occurred_at": "date",
        "amount": "amount",
        "transaction_type": "type",
        "direction": "direction",
        "account_name": "account",
        "merchant": "merchant",
        "external_ref": "external_ref",
    }

    resp = _preview(client, csv_text, mapping)
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["stats"]["duplicate_rows"] == 1
    assert payload["preview_rows"][0]["status"] == "duplicate"


def test_ledger_import_preview_owner_scope_isolated(admin_login):
    client = admin_login
    _create_account(client, "import-owner-admin")

    username = f"ledger_import_{uuid.uuid4().hex[:8]}"
    create_user = client.post("/api/admin/users", json={"username": username, "password": "u123456"})
    assert create_user.status_code == 200

    client.post("/api/auth/logout")
    user_login = client.post("/api/auth/login", json={"username": username, "password": "u123456"})
    assert user_login.status_code == 200
    _create_account(client, "import-owner-user")

    csv_text = "date,amount,type,direction,account\n2026-04-20 09:00:00,33,income,income,import-owner-user\n"
    mapping = {
        "occurred_at": "date",
        "amount": "amount",
        "transaction_type": "type",
        "direction": "direction",
        "account_name": "account",
    }
    resp = _preview(client, csv_text, mapping)
    assert resp.status_code == 200
    assert resp.json()["stats"]["valid_rows"] == 1
