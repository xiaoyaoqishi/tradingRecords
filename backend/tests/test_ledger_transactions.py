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


def test_ledger_transactions_crud_and_filter(admin_login):
    client = admin_login
    a1 = _create_account(client, "txn-a1")
    a2 = _create_account(client, "txn-a2")
    c1 = _create_category(client, "txn-expense")

    income = client.post(
        "/api/ledger/transactions",
        json={
            "occurred_at": "2026-04-20T09:00:00",
            "account_id": a1,
            "direction": "income",
            "transaction_type": "income",
            "amount": 1000,
            "currency": "CNY",
            "merchant": "salary",
        },
    )
    assert income.status_code == 200

    expense = client.post(
        "/api/ledger/transactions",
        json={
            "occurred_at": "2026-04-20T12:00:00",
            "account_id": a1,
            "category_id": c1,
            "direction": "expense",
            "transaction_type": "expense",
            "amount": 100,
            "currency": "CNY",
            "merchant": "lunch",
        },
    )
    assert expense.status_code == 200
    expense_id = expense.json()["id"]

    transfer = client.post(
        "/api/ledger/transactions",
        json={
            "occurred_at": "2026-04-20T13:00:00",
            "account_id": a1,
            "counterparty_account_id": a2,
            "direction": "neutral",
            "transaction_type": "transfer",
            "amount": 200,
            "currency": "CNY",
        },
    )
    assert transfer.status_code == 200

    bad_transfer = client.post(
        "/api/ledger/transactions",
        json={
            "occurred_at": "2026-04-20T13:00:00",
            "account_id": a1,
            "counterparty_account_id": a1,
            "direction": "neutral",
            "transaction_type": "transfer",
            "amount": 200,
            "currency": "CNY",
        },
    )
    assert bad_transfer.status_code == 400

    by_type = client.get("/api/ledger/transactions", params={"transaction_type": "expense"})
    assert by_type.status_code == 200
    assert by_type.json()["total"] >= 1
    assert all(x["transaction_type"] == "expense" for x in by_type.json()["items"])

    deleted = client.delete(f"/api/ledger/transactions/{expense_id}")
    assert deleted.status_code == 200

    after_delete = client.get("/api/ledger/transactions")
    ids = [x["id"] for x in after_delete.json()["items"]]
    assert expense_id not in ids
