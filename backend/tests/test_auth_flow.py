def test_auth_setup_login_check_logout(client):
    setup = client.post("/api/auth/setup", json={"username": "xiaoyao", "password": "admin123"})
    assert setup.status_code in (200, 400)

    login = client.post("/api/auth/login", json={"username": "xiaoyao", "password": "admin123"})
    assert login.status_code == 200
    assert login.json()["authenticated"] if "authenticated" in login.json() else True

    check = client.get("/api/auth/check")
    assert check.status_code == 200
    assert check.json().get("authenticated") is True

    logout = client.post("/api/auth/logout")
    assert logout.status_code == 200

    check2 = client.get("/api/auth/check")
    assert check2.status_code == 200
    assert check2.json().get("authenticated") is False
