from datetime import datetime


def _create_trade(client, symbol: str, price: float):
    payload = {
        "trade_date": "2026-04-20",
        "instrument_type": "futures",
        "symbol": symbol,
        "direction": "long",
        "open_time": datetime.utcnow().replace(microsecond=0).isoformat(),
        "open_price": price,
        "quantity": 1,
    }
    resp = client.post("/api/trades", json=payload)
    assert resp.status_code == 200
    return resp.json()


def test_trading_list_filter_by_symbol(admin_login):
    client = admin_login
    _create_trade(client, "FILTER_IF", 3500)
    _create_trade(client, "FILTER_RB", 3600)

    resp = client.get("/api/trades", params={"symbol": "FILTER_IF"})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert all(item["symbol"] == "FILTER_IF" for item in data)
