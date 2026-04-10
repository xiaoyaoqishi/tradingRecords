def _create_trade(client, notes=None):
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
        "notes": notes,
    }
    resp = client.post("/api/trades", json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def test_source_metadata_fallback_from_legacy_notes(app_client):
    trade_id = _create_trade(
        app_client,
        notes="来源券商: 宏源期货 | 来源: 日结单粘贴导入 | 其他备注: test",
    )
    resp = app_client.get(f"/api/trades/{trade_id}/source-metadata")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["exists_in_db"] is False
    assert body["trade_id"] == trade_id
    assert body["broker_name"] == "宏源期货"
    assert body["source_label"] == "日结单粘贴导入"
    assert body["derived_from_notes"] is True


def test_source_metadata_upsert_and_sources_endpoint_visibility(app_client):
    trade_id = _create_trade(app_client, notes="legacy note only")
    put_resp = app_client.put(
        f"/api/trades/{trade_id}/source-metadata",
        json={
            "broker_name": "MetaBroker",
            "source_label": "MetaSource",
            "import_channel": "manual_backfill",
            "source_note_snapshot": "legacy note only",
            "parser_version": "v1",
            "derived_from_notes": False,
        },
    )
    assert put_resp.status_code == 200, put_resp.text
    put_body = put_resp.json()
    assert put_body["exists_in_db"] is True
    assert put_body["broker_name"] == "MetaBroker"
    assert put_body["source_label"] == "MetaSource"
    assert put_body["derived_from_notes"] is False

    get_resp = app_client.get(f"/api/trades/{trade_id}/source-metadata")
    assert get_resp.status_code == 200, get_resp.text
    get_body = get_resp.json()
    assert get_body["id"] == put_body["id"]
    assert get_body["exists_in_db"] is True
    assert get_body["import_channel"] == "manual_backfill"

    source_resp = app_client.get("/api/trades/sources")
    assert source_resp.status_code == 200, source_resp.text
    items = source_resp.json()["items"]
    assert "MetaBroker" in items
    assert "MetaSource" in items
