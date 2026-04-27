import uuid


def test_admin_can_access_monitor_realtime(admin_login):
    client = admin_login

    realtime = client.get("/api/monitor/realtime")
    assert realtime.status_code == 200
    body = realtime.json()
    assert "cpu" in body
    assert "memory" in body
    assert "disk" in body
    assert "sampled_at" in body
    assert "platform" in body
    assert "architecture" in body


def test_non_admin_cannot_access_monitor_realtime(admin_login):
    client = admin_login
    username = f"monitor_user_{uuid.uuid4().hex[:8]}"

    create_user = client.post("/api/admin/users", json={"username": username, "password": "u123456"})
    assert create_user.status_code == 200

    client.post("/api/auth/logout")
    user_login = client.post("/api/auth/login", json={"username": username, "password": "u123456"})
    assert user_login.status_code == 200

    realtime = client.get("/api/monitor/realtime")
    assert realtime.status_code == 403


def test_monitor_admin_authz(admin_login):
    client = admin_login

    username = f"site_user_{uuid.uuid4().hex[:8]}"
    create_user = client.post("/api/admin/users", json={"username": username, "password": "u123456"})
    assert create_user.status_code == 200

    admin_sites = client.get("/api/monitor/sites")
    assert admin_sites.status_code == 200

    client.post("/api/auth/logout")
    user_login = client.post("/api/auth/login", json={"username": username, "password": "u123456"})
    assert user_login.status_code == 200

    user_sites = client.get("/api/monitor/sites")
    assert user_sites.status_code == 403
