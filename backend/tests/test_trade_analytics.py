import json


def _create_trade(client, payload):
    resp = client.post("/api/trades", json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_trade_analytics_endpoint_dimensions_and_coverage(app_client):
    t1 = _create_trade(
        app_client,
        {
            "trade_date": "2026-04-01",
            "instrument_type": "期货",
            "symbol": "IF",
            "contract": "IF2506",
            "direction": "做多",
            "open_time": "2026-04-01T09:00:00",
            "close_time": "2026-04-01T15:00:00",
            "open_price": 3500,
            "close_price": 3520,
            "quantity": 1,
            "status": "closed",
            "pnl": 30,
            "commission": 1,
            "is_planned": True,
            "strategy_type": "趋势突破",
            "market_condition": "趋势",
            "timeframe": "15分钟",
            "error_tags": json.dumps(["止损不坚决"]),
            "notes": "meta trade 1",
        },
    )
    t2 = _create_trade(
        app_client,
        {
            "trade_date": "2026-04-02",
            "instrument_type": "期货",
            "symbol": "IC",
            "contract": "IC2506",
            "direction": "做空",
            "open_time": "2026-04-02T09:00:00",
            "close_time": "2026-04-02T15:00:00",
            "open_price": 5200,
            "close_price": 5210,
            "quantity": 1,
            "status": "closed",
            "pnl": -10,
            "commission": 1,
            "is_planned": False,
            "strategy_type": "震荡反转",
            "market_condition": "震荡",
            "timeframe": "5分钟",
            "notes": "来源券商: LegacyBrokerA | 来源: LegacySourceA | legacy",
        },
    )
    t3 = _create_trade(
        app_client,
        {
            "trade_date": "2026-04-03",
            "instrument_type": "期货",
            "symbol": "IF",
            "contract": "IF2506",
            "direction": "做多",
            "open_time": "2026-04-03T09:30:00",
            "open_price": 3510,
            "quantity": 2,
            "status": "open",
            "is_overnight": False,
            "notes": "meta trade 2 open",
        },
    )

    put_source_1 = app_client.put(
        f"/api/trades/{t1['id']}/source-metadata",
        json={"broker_name": "MetaBrokerA", "source_label": "MetaSourceA"},
    )
    assert put_source_1.status_code == 200, put_source_1.text
    put_source_3 = app_client.put(
        f"/api/trades/{t3['id']}/source-metadata",
        json={"broker_name": "MetaBrokerA", "source_label": "MetaSourceA"},
    )
    assert put_source_3.status_code == 200, put_source_3.text

    review_1 = app_client.put(
        f"/api/trades/{t1['id']}/review",
        json={
            "opportunity_structure": "trend_initiation_pullback",
            "edge_source": "trend_continuation",
            "failure_type": "direction_wrong",
            "review_conclusion": "valid_pattern_valid_trade",
        },
    )
    assert review_1.status_code == 200, review_1.text
    review_2 = app_client.put(
        f"/api/trades/{t2['id']}/review",
        json={
            "opportunity_structure": "failed_breakout_reversal",
            "edge_source": "expectation_shift",
            "failure_type": "timing_wrong",
            "review_conclusion": "valid_pattern_invalid_trade",
        },
    )
    assert review_2.status_code == 200, review_2.text

    analytics_resp = app_client.get("/api/trades/analytics")
    assert analytics_resp.status_code == 200, analytics_resp.text
    body = analytics_resp.json()

    overview = body["overview"]
    assert overview["total_trades"] == 3
    assert overview["closed_trades"] == 2
    assert overview["open_trades"] == 1
    assert overview["win_count"] == 1
    assert overview["loss_count"] == 1
    assert overview["total_pnl"] == 20
    assert overview["open_position_count"] == 1

    coverage = body["coverage"]
    assert coverage["trade_review_count"] == 2
    assert coverage["source_metadata_count"] == 2
    assert coverage["legacy_source_only_count"] == 1

    by_source_keys = {x["key"] for x in body["dimensions"]["by_source"]}
    assert "MetaBrokerA / MetaSourceA" in by_source_keys
    assert "LegacyBrokerA / LegacySourceA" in by_source_keys

    by_failure_type = body["dimensions"]["by_review_field"]["failure_type"]
    failure_keys = {x["key"] for x in by_failure_type}
    assert "direction_wrong" in failure_keys
    assert "timing_wrong" in failure_keys

    by_review_conclusion = body["dimensions"]["by_review_field"]["review_conclusion"]
    conclusion_keys = {x["key"] for x in by_review_conclusion}
    assert "valid_pattern_valid_trade" in conclusion_keys
    assert "valid_pattern_invalid_trade" in conclusion_keys
