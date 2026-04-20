def test_trading_read_write(admin_login):
    client = admin_login
    create_payload = {
        "trade_date": "2026-04-20",
        "instrument_type": "futures",
        "symbol": "IF",
        "direction": "long",
        "open_time": "2026-04-20T09:30:00",
        "open_price": 3500,
        "quantity": 1,
    }
    created = client.post("/api/trades", json=create_payload)
    assert created.status_code == 200
    trade_id = created.json()["id"]

    one = client.get(f"/api/trades/{trade_id}")
    assert one.status_code == 200
    assert one.json()["symbol"] == "IF"

    listing = client.get("/api/trades")
    assert listing.status_code == 200
    assert isinstance(listing.json(), list)
    assert any(x["id"] == trade_id for x in listing.json())
