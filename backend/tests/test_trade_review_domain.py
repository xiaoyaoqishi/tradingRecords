def _create_trade(client):
    payload = {
        "trade_date": "2026-04-01",
        "instrument_type": "期货",
        "symbol": "IF",
        "contract": "IF2506",
        "direction": "做多",
        "open_time": "2026-04-01T09:00:00",
        "open_price": 3500,
        "quantity": 1,
        "status": "open",
    }
    resp = client.post("/api/trades", json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def test_trade_review_taxonomy_endpoint(app_client):
    resp = app_client.get("/api/trade-review-taxonomy")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "trend_initiation_pullback" in data["opportunity_structure"]
    assert "trend_continuation" in data["edge_source"]
    assert "direction_wrong" in data["failure_type"]
    assert "valid_pattern_valid_trade" in data["review_conclusion"]


def test_trade_review_upsert_and_get(app_client):
    trade_id = _create_trade(app_client)
    payload = {
        "opportunity_structure": "failed_breakout_reversal",
        "edge_source": "expectation_shift",
        "failure_type": "timing_wrong",
        "review_conclusion": "valid_pattern_invalid_trade",
        "entry_thesis": "setup had structure but entry was late",
        "management_actions": "reduced size after volatility expansion",
        "research_notes": "needs tighter trigger on second leg",
    }
    put_resp = app_client.put(f"/api/trades/{trade_id}/review", json=payload)
    assert put_resp.status_code == 200, put_resp.text
    body = put_resp.json()
    assert body["trade_id"] == trade_id
    assert body["failure_type"] == "timing_wrong"
    assert body["review_conclusion"] == "valid_pattern_invalid_trade"

    get_resp = app_client.get(f"/api/trades/{trade_id}/review")
    assert get_resp.status_code == 200, get_resp.text
    fetched = get_resp.json()
    assert fetched["id"] == body["id"]
    assert fetched["opportunity_structure"] == "failed_breakout_reversal"
    assert fetched["entry_thesis"] == payload["entry_thesis"]
    assert fetched["research_notes"] == payload["research_notes"]

    trade_resp = app_client.get(f"/api/trades/{trade_id}")
    assert trade_resp.status_code == 200, trade_resp.text
    assert trade_resp.json()["review_note"] is None


def test_trade_review_repeated_upsert_updates_same_row(app_client):
    trade_id = _create_trade(app_client)
    first = app_client.put(
        f"/api/trades/{trade_id}/review",
        json={
            "opportunity_structure": "trend_initiation_pullback",
            "failure_type": "timing_wrong",
            "entry_thesis": "first thesis",
        },
    )
    assert first.status_code == 200, first.text
    first_body = first.json()

    second = app_client.put(
        f"/api/trades/{trade_id}/review",
        json={
            "opportunity_structure": "failed_breakout_reversal",
            "failure_type": "execution_wrong",
            "entry_thesis": "updated thesis",
        },
    )
    assert second.status_code == 200, second.text
    second_body = second.json()

    assert second_body["id"] == first_body["id"]
    assert second_body["trade_id"] == trade_id
    assert second_body["opportunity_structure"] == "failed_breakout_reversal"
    assert second_body["failure_type"] == "execution_wrong"
    assert second_body["entry_thesis"] == "updated thesis"

    get_resp = app_client.get(f"/api/trades/{trade_id}/review")
    assert get_resp.status_code == 200, get_resp.text
    assert get_resp.json()["id"] == first_body["id"]


def test_deleting_trade_cascades_trade_review(app_client):
    trade_id = _create_trade(app_client)
    put_resp = app_client.put(
        f"/api/trades/{trade_id}/review",
        json={"review_conclusion": "valid_pattern_valid_trade"},
    )
    assert put_resp.status_code == 200, put_resp.text

    del_trade = app_client.delete(f"/api/trades/{trade_id}")
    assert del_trade.status_code == 200, del_trade.text

    trade_after = app_client.get(f"/api/trades/{trade_id}")
    assert trade_after.status_code == 404, trade_after.text
    review_after = app_client.get(f"/api/trades/{trade_id}/review")
    assert review_after.status_code == 404, review_after.text


def test_deleting_trade_review_does_not_delete_trade(app_client):
    trade_id = _create_trade(app_client)
    put_resp = app_client.put(
        f"/api/trades/{trade_id}/review",
        json={"edge_source": "trend_continuation"},
    )
    assert put_resp.status_code == 200, put_resp.text

    del_review = app_client.delete(f"/api/trades/{trade_id}/review")
    assert del_review.status_code == 200, del_review.text

    review_after = app_client.get(f"/api/trades/{trade_id}/review")
    assert review_after.status_code == 404, review_after.text
    trade_after = app_client.get(f"/api/trades/{trade_id}")
    assert trade_after.status_code == 200, trade_after.text
