from datetime import datetime


def test_recycle_trade_restore_chain(admin_login):
    client = admin_login
    payload = {
        "trade_date": "2026-04-20",
        "instrument_type": "futures",
        "symbol": "RECYCLE_FLOW",
        "direction": "long",
        "open_time": datetime.utcnow().replace(microsecond=0).isoformat(),
        "open_price": 3700,
        "quantity": 1,
    }
    created = client.post("/api/trades", json=payload)
    assert created.status_code == 200
    trade_id = created.json()["id"]

    deleted = client.delete(f"/api/trades/{trade_id}")
    assert deleted.status_code == 200

    recycled = client.get("/api/recycle/trades")
    assert recycled.status_code == 200
    assert any(item["id"] == trade_id for item in recycled.json())

    restored = client.post(f"/api/recycle/trades/{trade_id}/restore")
    assert restored.status_code == 200

    listing = client.get("/api/trades")
    assert listing.status_code == 200
    assert any(item["id"] == trade_id for item in listing.json())
