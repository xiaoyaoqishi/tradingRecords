import json

import pytest


PASTE_HEADER = "\t".join(
    [
        "交易日期",
        "合约",
        "买/卖",
        "投机（一般）/套保/套利",
        "成交价",
        "手数",
        "成交额",
        "开/平",
        "手续费",
        "平仓盈亏",
    ]
)


def make_row(
    trade_date: str,
    contract: str,
    side: str,
    price: float,
    qty: float,
    open_close: str,
    commission: float,
    pnl: float,
    category: str = "投机",
    turnover: float = 0,
) -> str:
    return (
        f"{trade_date}\t{contract}\t{side}\t{category}\t{price}\t{qty}\t"
        f"{turnover}\t{open_close}\t{commission}\t{pnl}"
    )


def import_paste(client, rows, broker=None, with_header=True):
    body_lines = [PASTE_HEADER] if with_header else []
    body_lines.extend(rows)
    payload = {"raw_text": "\n".join(body_lines)}
    if broker is not None:
        payload["broker"] = broker
    resp = client.post("/api/trades/import-paste", json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()


def list_trades(client, **params):
    merged = {"size": 200}
    merged.update(params)
    resp = client.get("/api/trades", params=merged)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_import_with_header_row(app_client):
    result = import_paste(
        app_client,
        [
            make_row(
                "2026-04-01",
                "IF2506",
                "买",
                3500,
                2,
                "开",
                1.2,
                0,
                turnover=700000,
            )
        ],
        broker="宏源期货",
        with_header=True,
    )

    assert result["inserted"] == 1
    assert result["skipped"] == 0
    assert result["errors"] == []
    assert app_client.get("/api/trades/count").json()["total"] == 1


def test_malformed_mixed_batch_is_partially_successful(app_client):
    result = import_paste(
        app_client,
        [
            make_row("2026-04-01", "IF2506", "买", 3500, 1, "开", 1, 0),
            make_row("bad-date", "IF2506", "买", 3500, 1, "开", 1, 0),
            make_row("2026-04-01", "IF2506", "未知", 3500, 1, "开", 1, 0),
            make_row("2026-04-01", "IF2506", "买", 3500, 0, "开", 1, 0),
            "2026-04-01\tIF2506\t买\t投机\t3500\t1",
        ],
        broker="宏源期货",
        with_header=True,
    )

    assert result["inserted"] == 1
    assert result["skipped"] == 0
    assert len(result["errors"]) == 4
    assert app_client.get("/api/trades/count").json()["total"] == 1


def test_custom_broker_source_behavior_and_scope(app_client):
    broker_a = "测试券商A"
    broker_b = "测试券商B"

    import_paste(
        app_client,
        [make_row("2026-04-01", "IF2506", "买", 3500, 1, "开", 1, 0)],
        broker=broker_a,
    )

    close_under_b = import_paste(
        app_client,
        [make_row("2026-04-02", "IF2506", "卖", 3520, 1, "平", 1, 20)],
        broker=broker_b,
    )
    assert close_under_b["inserted"] == 0
    assert len(close_under_b["errors"]) == 1
    assert "无足够对应开仓" in close_under_b["errors"][0]["reason"]

    close_under_a = import_paste(
        app_client,
        [make_row("2026-04-02", "IF2506", "卖", 3520, 1, "平", 1, 20)],
        broker=broker_a,
    )
    assert close_under_a["inserted"] == 1
    assert close_under_a["errors"] == []

    rows_a = list_trades(app_client, source_keyword=broker_a)
    rows_b = list_trades(app_client, source_keyword=broker_b)
    assert len(rows_a) == 1
    assert len(rows_b) == 0
    assert f"来源券商: {broker_a}" in (rows_a[0]["notes"] or "")

    count_a = app_client.get("/api/trades/count", params={"source_keyword": broker_a}).json()["total"]
    count_b = app_client.get("/api/trades/count", params={"source_keyword": broker_b}).json()["total"]
    assert count_a == 1
    assert count_b == 0


def test_open_row_dedup_baseline(app_client):
    broker = "去重券商"
    row = make_row("2026-04-01", "IF2506", "买", 3500, 1, "开", 1, 0)

    first = import_paste(app_client, [row], broker=broker)
    second = import_paste(app_client, [row], broker=broker)

    assert first["inserted"] == 1
    assert second["inserted"] == 0
    assert second["skipped"] == 1
    assert second["errors"] == []
    assert app_client.get("/api/trades/count", params={"source_keyword": broker}).json()["total"] == 1


def test_source_options_endpoint_discovers_imported_brokers(app_client):
    broker_a = "来源券商A"
    broker_b = "来源券商B"

    import_paste(
        app_client,
        [make_row("2026-04-01", "IF2506", "买", 3500, 1, "开", 1, 0)],
        broker=broker_a,
    )
    import_paste(
        app_client,
        [make_row("2026-04-01", "IC2506", "买", 5200, 1, "开", 1, 0)],
        broker=broker_b,
    )

    source_resp = app_client.get("/api/trades/sources")
    assert source_resp.status_code == 200, source_resp.text
    items = source_resp.json()["items"]
    assert broker_a in items
    assert broker_b in items


def test_close_matching_against_historical_opens(app_client):
    broker = "历史匹配券商"
    import_paste(
        app_client,
        [make_row("2026-04-01", "IF2506", "买", 3500, 1, "开", 1.5, 0)],
        broker=broker,
    )

    close_result = import_paste(
        app_client,
        [make_row("2026-04-02", "IF2506", "卖", 3525, 1, "平", 0.5, 25)],
        broker=broker,
    )
    assert close_result["inserted"] == 1
    assert close_result["errors"] == []

    positions = app_client.get("/api/trades/positions", params={"source_keyword": broker}).json()
    assert positions == []

    rows = list_trades(app_client, source_keyword=broker)
    assert len(rows) == 1
    assert rows[0]["status"] == "closed"
    assert rows[0]["pnl"] == pytest.approx(25.0)
    assert "来源: 自动平仓匹配" in (rows[0]["notes"] or "")


def test_close_rows_are_not_dedup_skipped(app_client):
    broker = "平仓非去重券商"
    import_paste(
        app_client,
        [make_row("2026-04-01", "IF2506", "买", 3500, 1, "开", 1, 0)],
        broker=broker,
    )
    close_row = make_row("2026-04-02", "IF2506", "卖", 3520, 1, "平", 1, 20)

    first_close = import_paste(app_client, [close_row], broker=broker)
    assert first_close["inserted"] == 1
    assert first_close["skipped"] == 0
    assert first_close["errors"] == []

    second_close = import_paste(app_client, [close_row], broker=broker)
    assert second_close["inserted"] == 0
    assert second_close["skipped"] == 0
    assert len(second_close["errors"]) == 1
    assert "平仓失败" in second_close["errors"][0]["reason"]


def test_same_batch_close_before_open_supported(app_client):
    broker = "同批次券商"
    close_first = make_row("2026-04-01", "IF2506", "卖", 3520, 1, "平", 0.3, 12)
    open_second = make_row("2026-04-01", "IF2506", "买", 3500, 1, "开", 0.7, 0)

    result = import_paste(app_client, [close_first, open_second], broker=broker)
    assert result["inserted"] == 2
    assert result["errors"] == []

    assert app_client.get("/api/trades/count", params={"source_keyword": broker}).json()["total"] == 1
    assert app_client.get("/api/trades/positions", params={"source_keyword": broker}).json() == []


def test_partial_close_split_behavior(app_client):
    broker = "部分平仓券商"
    import_paste(
        app_client,
        [make_row("2026-04-01", "IF2506", "买", 3500, 3, "开", 3.0, 0)],
        broker=broker,
    )

    close_result = import_paste(
        app_client,
        [make_row("2026-04-02", "IF2506", "卖", 3510, 1, "平", 0.5, 30)],
        broker=broker,
    )
    assert close_result["inserted"] == 1
    assert close_result["errors"] == []

    rows = list_trades(app_client, source_keyword=broker)
    assert len(rows) == 2

    open_row = next(r for r in rows if r["status"] == "open")
    closed_row = next(r for r in rows if r["status"] == "closed")

    assert open_row["quantity"] == pytest.approx(2.0)
    assert open_row["commission"] == pytest.approx(2.0)
    assert "部分平仓后自动拆分" in (open_row["notes"] or "")

    assert closed_row["quantity"] == pytest.approx(1.0)
    assert closed_row["commission"] == pytest.approx(1.5)
    assert closed_row["pnl"] == pytest.approx(30.0)
    assert "来源: 自动平仓拆分" in (closed_row["notes"] or "")


def test_trade_list_and_count_consistency(app_client):
    broker = "列表计数券商"
    import_paste(
        app_client,
        [
            make_row("2026-04-01", "IF2506", "买", 3500, 1, "开", 1, 0),
            make_row("2026-04-01", "IF2506", "买", 3490, 1, "开", 1, 0),
        ],
        broker=broker,
    )

    open_rows = list_trades(app_client, status="open", source_keyword=broker)
    open_total = app_client.get(
        "/api/trades/count",
        params={"status": "open", "source_keyword": broker},
    ).json()["total"]

    assert len(open_rows) == open_total


def test_statistics_and_positions_baseline_consistency(app_client):
    broker = "统计基线券商"
    import_paste(
        app_client,
        [make_row("2026-04-01", "IF2506", "买", 100, 2, "开", 2, 0)],
        broker=broker,
    )
    import_paste(
        app_client,
        [make_row("2026-04-02", "IF2506", "卖", 110, 1, "平", 1, 30)],
        broker=broker,
    )

    stats = app_client.get("/api/trades/statistics", params={"source_keyword": broker}).json()
    assert stats["total"] == 1
    assert stats["win_count"] == 1
    assert stats["loss_count"] == 0
    assert stats["total_pnl"] == pytest.approx(30.0)
    assert stats["pnl_by_symbol"][0]["symbol"] == "IF"
    assert stats["pnl_by_symbol"][0]["pnl"] == pytest.approx(30.0)

    positions = app_client.get("/api/trades/positions", params={"source_keyword": broker}).json()
    assert len(positions) == 1
    pos = positions[0]
    assert pos["symbol"] == "IF"
    assert pos["side"] == "做多"
    assert pos["net_quantity"] == pytest.approx(1.0)
    assert pos["avg_open_price"] == pytest.approx(100.0)


def test_trade_detail_error_tags_edit_compatibility(app_client):
    initial_tags = json.dumps(["追涨杀跌", "情绪化交易"], ensure_ascii=False)
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
        "error_tags": initial_tags,
    }

    create_resp = app_client.post("/api/trades", json=payload)
    assert create_resp.status_code == 200, create_resp.text
    trade = create_resp.json()
    trade_id = trade["id"]
    assert trade["error_tags"] == initial_tags
    assert json.loads(trade["error_tags"]) == ["追涨杀跌", "情绪化交易"]

    updated_tags = json.dumps(["止损不坚决"], ensure_ascii=False)
    update_resp = app_client.put(
        f"/api/trades/{trade_id}",
        json={"error_tags": updated_tags, "review_note": "更新后复盘"},
    )
    assert update_resp.status_code == 200, update_resp.text
    assert update_resp.json()["error_tags"] == updated_tags

    get_resp = app_client.get(f"/api/trades/{trade_id}")
    assert get_resp.status_code == 200, get_resp.text
    final_trade = get_resp.json()
    assert final_trade["error_tags"] == updated_tags
    assert json.loads(final_trade["error_tags"]) == ["止损不坚决"]
