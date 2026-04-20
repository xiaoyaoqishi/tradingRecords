import uuid


def test_ledger_user_cannot_read_admin_scope(admin_login):
    client = admin_login

    admin_account = client.post(
        "/api/ledger/accounts",
        json={"name": "authz-admin", "account_type": "cash", "currency": "CNY", "initial_balance": 0},
    )
    assert admin_account.status_code == 200

    username = f"ledger_authz_{uuid.uuid4().hex[:8]}"
    create_user = client.post("/api/admin/users", json={"username": username, "password": "u123456"})
    assert create_user.status_code == 200

    client.post("/api/auth/logout")
    user_login = client.post("/api/auth/login", json={"username": username, "password": "u123456"})
    assert user_login.status_code == 200

    user_list = client.get("/api/ledger/accounts")
    assert user_list.status_code == 200
    names = [x["name"] for x in user_list.json()["items"]]
    assert "authz-admin" not in names


def test_ledger_admin_can_read_cross_owner_scope(admin_login):
    client = admin_login

    username = f"ledger_cross_{uuid.uuid4().hex[:8]}"
    create_user = client.post("/api/admin/users", json={"username": username, "password": "u123456"})
    assert create_user.status_code == 200

    client.post("/api/auth/logout")
    user_login = client.post("/api/auth/login", json={"username": username, "password": "u123456"})
    assert user_login.status_code == 200

    user_account = client.post(
        "/api/ledger/accounts",
        json={"name": "authz-user", "account_type": "bank", "currency": "CNY", "initial_balance": 1},
    )
    assert user_account.status_code == 200

    client.post("/api/auth/logout")
    admin_login_resp = client.post("/api/auth/login", json={"username": "xiaoyao", "password": "admin123"})
    assert admin_login_resp.status_code == 200

    scoped_list = client.get("/api/ledger/accounts", params={"owner_role": "user"})
    assert scoped_list.status_code == 200
    names = [x["name"] for x in scoped_list.json()["items"]]
    assert "authz-user" in names
