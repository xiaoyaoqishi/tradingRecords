from datetime import datetime
import uuid


def test_user_guard_and_owner_role_isolation(admin_login):
    client = admin_login

    admin_trade = client.post(
        "/api/trades",
        json={
            "trade_date": "2026-04-20",
            "instrument_type": "futures",
            "symbol": "ADMIN_ONLY_SCOPE",
            "direction": "long",
            "open_time": datetime.utcnow().replace(microsecond=0).isoformat(),
            "open_price": 3800,
            "quantity": 1,
        },
    )
    assert admin_trade.status_code == 200
    admin_trade_id = admin_trade.json()["id"]

    username = f"user_{uuid.uuid4().hex[:8]}"
    create_user = client.post("/api/admin/users", json={"username": username, "password": "u123456"})
    assert create_user.status_code == 200

    client.post("/api/auth/logout")
    login_user = client.post("/api/auth/login", json={"username": username, "password": "u123456"})
    assert login_user.status_code == 200

    admin_api = client.get("/api/admin/users")
    assert admin_api.status_code == 403

    monitor_api = client.get("/api/monitor/sites")
    assert monitor_api.status_code == 403

    trades_for_user = client.get("/api/trades")
    assert trades_for_user.status_code == 200
    ids = [item["id"] for item in trades_for_user.json()]
    assert admin_trade_id not in ids
