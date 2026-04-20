def test_monitor_admin_authz(admin_login):
    client = admin_login

    create_user = client.post("/api/admin/users", json={"username": "u1", "password": "u123456"})
    assert create_user.status_code == 200

    admin_sites = client.get("/api/monitor/sites")
    assert admin_sites.status_code == 200

    client.post("/api/auth/logout")
    user_login = client.post("/api/auth/login", json={"username": "u1", "password": "u123456"})
    assert user_login.status_code == 200

    user_sites = client.get("/api/monitor/sites")
    assert user_sites.status_code == 403
