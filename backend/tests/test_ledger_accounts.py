import uuid


def test_ledger_account_create_list_and_name_unique(admin_login):
    client = admin_login

    create = client.post(
        "/api/ledger/accounts",
        json={
            "name": "cash-main",
            "account_type": "cash",
            "currency": "CNY",
            "initial_balance": 100,
        },
    )
    assert create.status_code == 200
    assert create.json()["name"] == "cash-main"

    listing = client.get("/api/ledger/accounts")
    assert listing.status_code == 200
    items = listing.json()["items"]
    assert any(x["name"] == "cash-main" for x in items)

    dup = client.post(
        "/api/ledger/accounts",
        json={
            "name": "cash-main",
            "account_type": "cash",
            "currency": "CNY",
            "initial_balance": 0,
        },
    )
    assert dup.status_code == 400


def test_ledger_account_owner_scope(admin_login):
    client = admin_login

    admin_create = client.post(
        "/api/ledger/accounts",
        json={"name": "admin-visible-only", "account_type": "bank", "currency": "CNY", "initial_balance": 0},
    )
    assert admin_create.status_code == 200

    username = f"ledger_u_{uuid.uuid4().hex[:8]}"
    create_user = client.post("/api/admin/users", json={"username": username, "password": "u123456"})
    assert create_user.status_code == 200

    client.post("/api/auth/logout")
    login_user = client.post("/api/auth/login", json={"username": username, "password": "u123456"})
    assert login_user.status_code == 200

    user_create = client.post(
        "/api/ledger/accounts",
        json={"name": "user-visible", "account_type": "cash", "currency": "CNY", "initial_balance": 8},
    )
    assert user_create.status_code == 200

    user_list = client.get("/api/ledger/accounts")
    assert user_list.status_code == 200
    names = [x["name"] for x in user_list.json()["items"]]
    assert "user-visible" in names
    assert "admin-visible-only" not in names
