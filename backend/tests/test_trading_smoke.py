def test_trading_read_write(admin_login):
    client = admin_login
    create_payload = {
        "instrument_type": "期货",
        "symbol": "IF",
        "direction": "long",
        "open_time": "2026-04-20T09:30:00",
        "open_price": 3500,
        "stop_loss_point": 3480,
        "target_point": 3550,
        "capital_percentage": 12.5,
    }
    created = client.post("/api/trades", json=create_payload)
    assert created.status_code == 200
    trade_id = created.json()["id"]

    one = client.get(f"/api/trades/{trade_id}")
    assert one.status_code == 200
    assert one.json()["symbol"] == "IF"
    assert one.json()["trade_date"] == "2026-04-20"

    history = client.get(f"/api/trades/{trade_id}/risk-point-history")
    assert history.status_code == 200
    assert len(history.json()) == 1
    assert history.json()[0]["stop_loss_point"] == 3480
    assert history.json()[0]["target_point"] == 3550
    assert history.json()[0]["capital_percentage"] == 12.5
    assert history.json()[0]["recorded_at"].endswith("+08:00")

    updated = client.put(
        f"/api/trades/{trade_id}",
        json={"stop_loss_point": 3490, "target_point": 3560, "capital_percentage": 18},
    )
    assert updated.status_code == 200
    assert updated.json()["stop_loss_point"] == 3490

    updated_history = client.get(f"/api/trades/{trade_id}/risk-point-history")
    assert updated_history.status_code == 200
    assert len(updated_history.json()) == 2
    assert updated_history.json()[0]["stop_loss_point"] == 3490
    assert updated_history.json()[0]["target_point"] == 3560
    assert updated_history.json()[0]["capital_percentage"] == 18
    assert updated_history.json()[1]["stop_loss_point"] == 3480
    assert updated_history.json()[1]["target_point"] == 3550
    assert updated_history.json()[1]["capital_percentage"] == 12.5

    unchanged = client.put(
        f"/api/trades/{trade_id}",
        json={"stop_loss_point": 3490, "target_point": 3560, "capital_percentage": 18},
    )
    assert unchanged.status_code == 200
    unchanged_history = client.get(f"/api/trades/{trade_id}/risk-point-history")
    assert len(unchanged_history.json()) == 2

    capital_only_update = client.put(
        f"/api/trades/{trade_id}",
        json={"capital_percentage": 22},
    )
    assert capital_only_update.status_code == 200
    capital_history = client.get(f"/api/trades/{trade_id}/risk-point-history")
    assert len(capital_history.json()) == 3
    assert capital_history.json()[0]["stop_loss_point"] == 3490
    assert capital_history.json()[0]["target_point"] == 3560
    assert capital_history.json()[0]["capital_percentage"] == 22

    listing = client.get("/api/trades")
    assert listing.status_code == 200
    assert isinstance(listing.json(), list)
    assert any(x["id"] == trade_id for x in listing.json())


def test_trade_requires_initial_risk_points(admin_login):
    response = admin_login.post(
        "/api/trades",
        json={
            "trade_date": "2026-04-20",
            "instrument_type": "期货",
            "symbol": "IF",
            "direction": "long",
            "open_time": "2026-04-20T09:30:00",
            "open_price": 3500,
            "stop_loss_point": 3480,
            "target_point": 3550,
        },
    )
    assert response.status_code == 422

    invalid_percentage = admin_login.post(
        "/api/trades",
        json={
            "instrument_type": "期货",
            "symbol": "IF",
            "direction": "long",
            "open_time": "2026-04-20T09:30:00",
            "open_price": 3500,
            "stop_loss_point": 3480,
            "target_point": 3550,
            "capital_percentage": 101,
        },
    )
    assert invalid_percentage.status_code == 422


def test_trade_update_derives_status_and_requires_complete_close_fields(admin_login):
    created = admin_login.post(
        "/api/trades",
        json={
            "instrument_type": "期货",
            "symbol": "AUTO_STATUS_IF",
            "direction": "long",
            "open_time": "2026-04-20T09:30:00",
            "open_price": 3500,
            "stop_loss_point": 3480,
            "target_point": 3550,
            "capital_percentage": 12.5,
        },
    )
    assert created.status_code == 200
    trade_id = created.json()["id"]

    status_only = admin_login.put(f"/api/trades/{trade_id}", json={"status": "closed"})
    assert status_only.status_code == 200
    assert status_only.json()["status"] == "open"

    close_time_only = admin_login.put(
        f"/api/trades/{trade_id}",
        json={"close_time": "2026-04-20T14:30:00"},
    )
    assert close_time_only.status_code == 400
    assert "平仓时间和平仓价必须同时填写" in close_time_only.json()["error"]["message"]

    close_price_only = admin_login.put(f"/api/trades/{trade_id}", json={"close_price": 3560})
    assert close_price_only.status_code == 400

    missing_close_amounts = admin_login.put(
        f"/api/trades/{trade_id}",
        json={"close_time": "2026-04-20T14:30:00", "close_price": 3560},
    )
    assert missing_close_amounts.status_code == 400
    assert "手续费和盈亏金额" in missing_close_amounts.json()["error"]["message"]

    closed = admin_login.put(
        f"/api/trades/{trade_id}",
        json={
            "close_time": "2026-04-20T14:30:00",
            "close_price": 3560,
            "commission": 5,
            "pnl": 55,
            "status": "open",
        },
    )
    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"

    reopened = admin_login.put(
        f"/api/trades/{trade_id}",
        json={"close_time": None, "close_price": None, "status": "closed"},
    )
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "open"


def test_trade_create_derives_status_and_requires_close_amounts(admin_login):
    payload = {
        "instrument_type": "期货",
        "symbol": "CREATE_AUTO_STATUS_IF",
        "direction": "long",
        "open_time": "2026-04-20T09:30:00",
        "open_price": 3500,
        "stop_loss_point": 3480,
        "target_point": 3550,
        "capital_percentage": 12.5,
    }

    ignored_manual_status = admin_login.post("/api/trades", json={**payload, "status": "closed"})
    assert ignored_manual_status.status_code == 200
    assert ignored_manual_status.json()["status"] == "open"

    incomplete_close = admin_login.post(
        "/api/trades",
        json={**payload, "close_time": "2026-04-20T14:30:00"},
    )
    assert incomplete_close.status_code == 400
    assert "平仓时间和平仓价必须同时填写" in incomplete_close.json()["error"]["message"]

    missing_amounts = admin_login.post(
        "/api/trades",
        json={
            **payload,
            "close_time": "2026-04-20T14:30:00",
            "close_price": 3560,
        },
    )
    assert missing_amounts.status_code == 400
    assert "手续费和盈亏金额" in missing_amounts.json()["error"]["message"]

    closed = admin_login.post(
        "/api/trades",
        json={
            **payload,
            "close_time": "2026-04-20T14:30:00",
            "close_price": 3560,
            "commission": 0,
            "pnl": 0,
            "status": "open",
        },
    )
    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"


def test_crypto_trade_stores_usdt_and_uses_cny_for_analytics(admin_login):
    created = admin_login.post(
        "/api/trades",
        json={
            "instrument_type": "加密货币",
            "symbol": "BTCUSDT",
            "direction": "做多",
            "open_time": "2026-08-05T09:30:00",
            "close_time": "2026-08-05T10:30:00",
            "open_price": 115000,
            "close_price": 116000,
            "stop_loss_point": 114000,
            "target_point": 117000,
            "capital_percentage": 10,
            "commission_usdt": 2.5,
            "pnl_usdt": 100,
            "usd_cny_rate": 7.2,
            "status": "closed",
        },
    )
    assert created.status_code == 200
    payload = created.json()
    assert payload["commission_usdt"] == 2.5
    assert payload["commission"] == 18.0
    assert payload["pnl_usdt"] == 100
    assert payload["pnl"] == 720.0
    assert payload["usd_cny_rate"] == 7.2

    analytics = admin_login.get("/api/trades/analytics", params={"instrument_type": "加密货币"})
    assert analytics.status_code == 200
    overview = analytics.json()["overview"]
    assert overview["total_pnl"] == 720.0
    assert overview["total_commission"] == 18.0

    updated = admin_login.put(
        f"/api/trades/{payload['id']}",
        json={"pnl_usdt": -10, "usd_cny_rate": 7.1},
    )
    assert updated.status_code == 200
    assert updated.json()["pnl_usdt"] == -10
    assert updated.json()["pnl"] == -71.0
    assert updated.json()["commission"] == 17.75


def test_crypto_trade_rejects_usdt_without_exchange_rate(admin_login):
    response = admin_login.post(
        "/api/trades",
        json={
            "instrument_type": "加密货币",
            "symbol": "ETHUSDT",
            "direction": "做多",
            "open_time": "2026-08-05T09:30:00",
            "open_price": 3600,
            "stop_loss_point": 3500,
            "target_point": 3800,
            "capital_percentage": 8,
            "pnl_usdt": 10,
        },
    )
    assert response.status_code == 400
    assert "汇率" in response.json()["error"]["message"]
