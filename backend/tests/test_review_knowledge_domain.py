def _create_trade(client, symbol="IF", contract="IF2506", direction="做多", open_price=3500):
    payload = {
        "trade_date": "2026-04-01",
        "instrument_type": "期货",
        "symbol": symbol,
        "contract": contract,
        "direction": direction,
        "open_time": "2026-04-01T09:00:00",
        "open_price": open_price,
        "quantity": 1,
        "status": "open",
    }
    resp = client.post("/api/trades", json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def _create_review(client, review_type="daily", review_scope="periodic"):
    payload = {
        "review_type": review_type,
        "review_scope": review_scope,
        "review_date": "2026-04-02",
        "title": "复盘主题",
        "summary": "summary",
    }
    resp = client.post("/api/reviews", json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_review_trade_links_can_be_upserted_and_replaced(app_client):
    trade_a = _create_trade(app_client, symbol="IF", contract="IF2506")
    trade_b = _create_trade(app_client, symbol="IC", contract="IC2506", open_price=5200)
    review = _create_review(app_client)
    review_id = review["id"]

    first_upsert = app_client.put(
        f"/api/reviews/{review_id}/trade-links",
        json={
            "trade_links": [
                {"trade_id": trade_a, "role": "best_trade", "notes": "A is best"},
                {"trade_id": trade_b, "role": "linked_trade", "notes": "B related"},
            ]
        },
    )
    assert first_upsert.status_code == 200, first_upsert.text
    body = first_upsert.json()
    assert sorted(body["linked_trade_ids"]) == sorted([trade_a, trade_b])
    assert len(body["trade_links"]) == 2
    first_summary = body["trade_links"][0]["trade_summary"]
    assert first_summary is not None
    assert "symbol" in first_summary
    assert "source_display" in first_summary

    second_upsert = app_client.put(
        f"/api/reviews/{review_id}/trade-links",
        json={
            "trade_links": [
                {"trade_id": trade_b, "role": "worst_trade", "notes": "updated role"},
                {"trade_id": trade_b, "role": "representative_trade", "notes": "duplicate should dedup"},
            ]
        },
    )
    assert second_upsert.status_code == 200, second_upsert.text
    body2 = second_upsert.json()
    assert body2["linked_trade_ids"] == [trade_b]
    assert len(body2["trade_links"]) == 1
    assert body2["trade_links"][0]["role"] == "representative_trade"

    get_review = app_client.get(f"/api/reviews/{review_id}")
    assert get_review.status_code == 200, get_review.text
    fetched = get_review.json()
    assert fetched["linked_trade_ids"] == [trade_b]
    assert len(fetched["trade_links"]) == 1
    assert fetched["trade_links"][0]["trade_id"] == trade_b
    assert fetched["trade_links"][0]["trade_summary"]["trade_id"] == trade_b


def test_review_scope_invalid_value_is_normalized_to_custom(app_client):
    created = _create_review(app_client, review_scope="random-scope")
    assert created["review_scope"] == "custom"

    rid = created["id"]
    updated = app_client.put(
        f"/api/reviews/{rid}",
        json={"review_scope": "still-invalid"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["review_scope"] == "custom"


def test_review_list_supports_scope_filter(app_client):
    _create_review(app_client, review_type="daily", review_scope="periodic")
    _create_review(app_client, review_type="daily", review_scope="themed")

    themed_resp = app_client.get("/api/reviews", params={"review_type": "daily", "review_scope": "themed"})
    assert themed_resp.status_code == 200, themed_resp.text
    themed_rows = themed_resp.json()
    assert len(themed_rows) == 1
    assert themed_rows[0]["review_scope"] == "themed"


def test_review_tags_array_and_filter(app_client):
    create_resp = app_client.post(
        "/api/reviews",
        json={
            "review_type": "weekly",
            "review_scope": "themed",
            "review_date": "2026-04-02",
            "title": "tagged review",
            "tags": ["趋势", "执行"],
        },
    )
    assert create_resp.status_code == 200, create_resp.text
    review = create_resp.json()
    assert set(review["tags"]) == {"趋势", "执行"}
    assert review["tags_text"] == "趋势,执行"

    update_resp = app_client.put(
        f"/api/reviews/{review['id']}",
        json={"tags": ["执行", "风控"]},
    )
    assert update_resp.status_code == 200, update_resp.text
    updated = update_resp.json()
    assert set(updated["tags"]) == {"执行", "风控"}
    assert updated["tags_text"] == "执行,风控"

    by_tag = app_client.get("/api/reviews", params={"tag": "风控", "size": 200})
    assert by_tag.status_code == 200, by_tag.text
    rows = by_tag.json()
    assert len(rows) == 1
    assert rows[0]["id"] == review["id"]


def test_knowledge_item_crud_filters_and_categories(app_client):
    create_a = app_client.post(
        "/api/knowledge-items",
        json={
            "category": "pattern_dictionary",
            "title": "趋势启动回调",
            "summary": "setup summary",
            "content": "entry and invalidation",
            "tags": ["trend", "pullback"],
            "status": "active",
            "priority": "high",
        },
    )
    assert create_a.status_code == 200, create_a.text
    item_a = create_a.json()
    assert set(item_a["tags"]) == {"trend", "pullback"}
    assert item_a["tags_text"] == "trend,pullback"

    create_b = app_client.post(
        "/api/knowledge-items",
        json={
            "category": "broker_reference",
            "title": "宏源期货通道备注",
            "summary": "broker memo",
            "content": "night session limits",
            "tags": ["broker", "infra"],
            "status": "archived",
            "priority": "low",
        },
    )
    assert create_b.status_code == 200, create_b.text
    item_b = create_b.json()

    categories_resp = app_client.get("/api/knowledge-items/categories")
    assert categories_resp.status_code == 200, categories_resp.text
    categories = categories_resp.json()["items"]
    assert "pattern_dictionary" in categories
    assert "broker_reference" in categories

    list_pattern = app_client.get("/api/knowledge-items", params={"category": "pattern_dictionary"})
    assert list_pattern.status_code == 200, list_pattern.text
    ids_pattern = [x["id"] for x in list_pattern.json()]
    assert item_a["id"] in ids_pattern
    assert item_b["id"] not in ids_pattern

    list_archived = app_client.get("/api/knowledge-items", params={"status": "archived"})
    assert list_archived.status_code == 200, list_archived.text
    assert item_b["id"] in [x["id"] for x in list_archived.json()]

    keyword_search = app_client.get("/api/knowledge-items", params={"q": "pullback"})
    assert keyword_search.status_code == 200, keyword_search.text
    assert item_a["id"] in [x["id"] for x in keyword_search.json()]

    by_tag = app_client.get("/api/knowledge-items", params={"tag": "infra"})
    assert by_tag.status_code == 200, by_tag.text
    by_tag_rows = by_tag.json()
    assert len(by_tag_rows) == 1
    assert by_tag_rows[0]["id"] == item_b["id"]

    update_a = app_client.put(
        f"/api/knowledge-items/{item_a['id']}",
        json={"status": "archived", "next_action": "next week retest", "tags": ["trend", "timing"]},
    )
    assert update_a.status_code == 200, update_a.text
    assert update_a.json()["status"] == "archived"
    assert update_a.json()["next_action"] == "next week retest"
    assert set(update_a.json()["tags"]) == {"trend", "timing"}

    delete_b = app_client.delete(f"/api/knowledge-items/{item_b['id']}")
    assert delete_b.status_code == 200, delete_b.text
    get_b = app_client.get(f"/api/knowledge-items/{item_b['id']}")
    assert get_b.status_code == 404, get_b.text
