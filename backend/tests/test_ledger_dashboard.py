def test_ledger_dashboard_summary_and_recent(admin_login):
    client = admin_login

    account = client.post(
        "/api/ledger/accounts",
        json={"name": "dash-a1", "account_type": "cash", "currency": "CNY", "initial_balance": 100},
    )
    assert account.status_code == 200
    account_id = account.json()["id"]

    category = client.post(
        "/api/ledger/categories",
        json={"name": "dash-c1", "category_type": "expense", "sort_order": 1, "is_active": True},
    )
    assert category.status_code == 200
    category_id = category.json()["id"]

    tx_income = client.post(
        "/api/ledger/transactions",
        json={
            "occurred_at": "2026-04-20T09:00:00",
            "account_id": account_id,
            "direction": "income",
            "transaction_type": "income",
            "amount": 500,
            "currency": "CNY",
            "merchant": "salary",
        },
    )
    assert tx_income.status_code == 200

    tx_expense = client.post(
        "/api/ledger/transactions",
        json={
            "occurred_at": "2026-04-20T10:00:00",
            "account_id": account_id,
            "category_id": category_id,
            "direction": "expense",
            "transaction_type": "expense",
            "amount": 200,
            "currency": "CNY",
            "merchant": "food",
        },
    )
    assert tx_expense.status_code == 200

    dashboard = client.get("/api/ledger/dashboard")
    assert dashboard.status_code == 200
    payload = dashboard.json()

    assert payload["income_total"] == 500
    assert payload["expense_total"] == 200
    assert payload["net_cashflow"] == 300

    accounts = payload["accounts_summary"]
    assert any(x["id"] == account_id and x["current_balance"] == 400 for x in accounts)

    recents = payload["recent_transactions"]
    assert len(recents) >= 2
