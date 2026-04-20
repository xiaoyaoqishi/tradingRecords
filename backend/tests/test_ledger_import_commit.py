import json
import uuid


def _create_account(client, name):
    r = client.post(
        "/api/ledger/accounts",
        json={"name": name, "account_type": "cash", "currency": "CNY", "initial_balance": 0},
    )
    assert r.status_code == 200
    return r.json()["id"]


def _preview(client, csv_text, mapping):
    return client.post(
        "/api/ledger/import/preview",
        data={
            "delimiter": ",",
            "encoding": "utf-8",
            "has_header": "true",
            "mapping_json": json.dumps(mapping, ensure_ascii=False),
            "preview_limit": "100",
        },
        files={"file": ("commit.csv", csv_text.encode("utf-8"), "text/csv")},
    )


def test_ledger_import_commit_create_and_skip_duplicate(admin_login):
    client = admin_login
    account_id = _create_account(client, "import-commit-a1")

    existed = client.post(
        "/api/ledger/transactions",
        json={
            "occurred_at": "2026-04-21T08:00:00",
            "account_id": account_id,
            "direction": "income",
            "transaction_type": "income",
            "amount": 20,
            "currency": "CNY",
            "merchant": "dup-m",
            "external_ref": "dup-ref",
        },
    )
    assert existed.status_code == 200

    csv_text = "date,amount,type,direction,account,merchant,external_ref\n2026-04-21 08:00:00,20,income,income,import-commit-a1,dup-m,dup-ref\n2026-04-21 09:00:00,50,income,income,import-commit-a1,salary,sal-1\n"
    mapping = {
        "occurred_at": "date",
        "amount": "amount",
        "transaction_type": "type",
        "direction": "direction",
        "account_name": "account",
        "merchant": "merchant",
        "external_ref": "external_ref",
    }

    preview = _preview(client, csv_text, mapping)
    assert preview.status_code == 200

    commit = client.post(
        "/api/ledger/import/commit",
        json={
            "records": preview.json()["preview_rows"],
            "skip_duplicates": True,
            "skip_invalid": True,
        },
    )
    assert commit.status_code == 200
    payload = commit.json()
    assert payload["created_count"] == 1
    assert payload["skipped_duplicate_count"] >= 1

    tx = client.get("/api/ledger/transactions", params={"source": "import_csv"})
    assert tx.status_code == 200
    assert any(x["merchant"] == "salary" and x["source"] == "import_csv" for x in tx.json()["items"])


def test_ledger_import_commit_skip_invalid(admin_login):
    client = admin_login
    _create_account(client, "import-commit-a2")

    commit = client.post(
        "/api/ledger/import/commit",
        json={
            "records": [
                {
                    "row_no": 1,
                    "record": {
                        "occurred_at": "",
                        "amount": "abc",
                        "transaction_type": "expense",
                        "direction": "expense",
                        "account_id": None,
                    },
                }
            ],
            "skip_duplicates": True,
            "skip_invalid": True,
        },
    )
    assert commit.status_code == 200
    payload = commit.json()
    assert payload["created_count"] == 0
    assert payload["skipped_invalid_count"] == 1


def test_ledger_import_commit_owner_scope_isolated(admin_login):
    client = admin_login
    admin_account_id = _create_account(client, "import-commit-admin")

    existed = client.post(
        "/api/ledger/transactions",
        json={
            "occurred_at": "2026-04-21T10:00:00",
            "account_id": admin_account_id,
            "direction": "income",
            "transaction_type": "income",
            "amount": 30,
            "currency": "CNY",
            "merchant": "same-row",
        },
    )
    assert existed.status_code == 200

    username = f"ledger_import_commit_{uuid.uuid4().hex[:8]}"
    create_user = client.post("/api/admin/users", json={"username": username, "password": "u123456"})
    assert create_user.status_code == 200
    client.post("/api/auth/logout")
    user_login = client.post("/api/auth/login", json={"username": username, "password": "u123456"})
    assert user_login.status_code == 200
    _create_account(client, "import-commit-user")

    csv_text = "date,amount,type,direction,account,merchant\n2026-04-21 10:00:00,30,income,income,import-commit-user,same-row\n"
    mapping = {
        "occurred_at": "date",
        "amount": "amount",
        "transaction_type": "type",
        "direction": "direction",
        "account_name": "account",
        "merchant": "merchant",
    }

    preview = _preview(client, csv_text, mapping)
    assert preview.status_code == 200
    commit = client.post(
        "/api/ledger/import/commit",
        json={"records": preview.json()["preview_rows"], "skip_duplicates": True, "skip_invalid": True},
    )
    assert commit.status_code == 200
    assert commit.json()["created_count"] == 1
