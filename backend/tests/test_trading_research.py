def test_trading_research_crud_links_and_recycle(admin_login):
    client = admin_login

    folder = client.post("/api/trades/research/folders", json={"name": "策略研究"})
    assert folder.status_code == 200
    folder_id = folder.json()["id"]

    child_folder = client.post(
        "/api/trades/research/folders",
        json={"name": "证据", "parent_id": folder_id},
    )
    assert child_folder.status_code == 200
    cycle = client.put(
        f"/api/trades/research/folders/{folder_id}",
        json={"parent_id": child_folder.json()["id"]},
    )
    assert cycle.status_code == 400

    alpha = client.post(
        "/api/trades/research/documents",
        json={
            "folder_id": folder_id,
            "title": "Alpha 假设",
            "content": "<p>验证 [[Beta 证据]]</p>",
            "tags": ["假设", "趋势"],
            "is_pinned": True,
        },
    )
    assert alpha.status_code == 200
    alpha_id = alpha.json()["id"]
    assert alpha.json()["tags"] == ["假设", "趋势"]

    beta = client.post(
        "/api/trades/research/documents",
        json={"folder_id": folder_id, "title": "Beta 证据", "content": "<p>样本证据</p>"},
    )
    assert beta.status_code == 200
    beta_id = beta.json()["id"]

    backlinks = client.get(f"/api/trades/research/documents/{beta_id}/backlinks")
    assert backlinks.status_code == 200
    assert backlinks.json()[0]["document_id"] == alpha_id

    searched = client.get("/api/trades/research/documents", params={"keyword": "Alpha"})
    assert searched.status_code == 200
    assert searched.json()["total"] == 1

    updated = client.put(
        f"/api/trades/research/documents/{alpha_id}",
        json={"title": "Alpha 验证", "is_pinned": False},
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Alpha 验证"

    deleted = client.delete(f"/api/trades/research/documents/{alpha_id}")
    assert deleted.status_code == 200
    assert client.get(f"/api/trades/research/documents/{alpha_id}").status_code == 404

    recycle = client.get("/api/trades/research/recycle")
    assert recycle.status_code == 200
    assert any(item["id"] == alpha_id for item in recycle.json())

    restored = client.post(f"/api/trades/research/recycle/{alpha_id}/restore")
    assert restored.status_code == 200
    assert client.get(f"/api/trades/research/documents/{alpha_id}").status_code == 200


def test_trading_research_document_can_reference_multiple_trades(admin_login):
    client = admin_login
    folder_id = client.post("/api/trades/research/folders", json={"name": "交易样本"}).json()["id"]

    def create_trade(symbol, open_time, direction, open_price):
        response = client.post(
            "/api/trades",
            json={
                "instrument_type": "期货",
                "symbol": symbol,
                "direction": direction,
                "open_time": open_time,
                "open_price": open_price,
                "stop_loss_point": open_price - 10,
                "target_point": open_price + 20,
                "capital_percentage": 10,
            },
        )
        assert response.status_code == 200
        return response.json()["id"]

    first_trade_id = create_trade("IF", "2026-07-01T09:30:00", "long", 3500)
    second_trade_id = create_trade("AU", "2026-07-02T09:30:00", "short", 780)

    created = client.post(
        "/api/trades/research/documents",
        json={
            "folder_id": folder_id,
            "title": "多交易样本复盘",
            "trade_ids": [first_trade_id, second_trade_id, first_trade_id],
        },
    )
    assert created.status_code == 200
    document_id = created.json()["id"]
    assert created.json()["trade_ids"] == [first_trade_id, second_trade_id]
    assert [item["trade_id"] for item in created.json()["related_trades"]] == [first_trade_id, second_trade_id]

    second_document = client.post(
        "/api/trades/research/documents",
        json={
            "folder_id": folder_id,
            "title": "第二篇交易复盘",
            "trade_ids": [first_trade_id],
        },
    )
    assert second_document.status_code == 200
    linked_research = client.get(f"/api/trades/{first_trade_id}/research-documents")
    assert linked_research.status_code == 200
    assert {item["title"] for item in linked_research.json()} == {"多交易样本复盘", "第二篇交易复盘"}

    updated = client.put(
        f"/api/trades/research/documents/{document_id}",
        json={"trade_ids": [second_trade_id]},
    )
    assert updated.status_code == 200
    assert updated.json()["trade_ids"] == [second_trade_id]
    assert updated.json()["related_trades"][0]["symbol"] == "AU"
    assert client.get(f"/api/trades/{first_trade_id}/research-documents").json() == [
        {"document_id": second_document.json()["id"], "title": "第二篇交易复盘"}
    ]

    rejected = client.put(
        f"/api/trades/research/documents/{document_id}",
        json={"trade_ids": [999999]},
    )
    assert rejected.status_code == 400
    assert client.get(f"/api/trades/research/documents/{document_id}").json()["trade_ids"] == [second_trade_id]

    assert client.delete(f"/api/trades/{second_trade_id}").status_code == 200
    assert client.get(f"/api/trades/research/documents/{document_id}").json()["trade_ids"] == []
    assert client.post(f"/api/recycle/trades/{second_trade_id}/restore").status_code == 200
    assert client.get(f"/api/trades/research/documents/{document_id}").json()["trade_ids"] == [second_trade_id]
    assert client.delete(f"/api/trades/{second_trade_id}").status_code == 200
    assert client.delete(f"/api/recycle/trades/{second_trade_id}/purge").status_code == 200
    assert client.get(f"/api/trades/research/documents/{document_id}").json()["trade_ids"] == []


def test_legacy_trading_notes_are_migrated_idempotently(admin_login):
    import core.db as core_db
    from models import Note, Notebook, TradingResearchDocument, TradingResearchFolder
    from trading.research_service import migrate_legacy_trading_research

    db = core_db.SessionLocal()
    try:
        legacy_folder = Notebook(name="旧研究", module_scope="trading", owner_role="admin")
        db.add(legacy_folder)
        db.flush()
        legacy_document = Note(
            notebook_id=legacy_folder.id,
            title="旧研究内容",
            content="<p>需要迁移</p>",
            note_type="doc",
            module_scope="trading",
            owner_role="admin",
        )
        db.add(legacy_document)
        db.commit()
        legacy_folder_id = legacy_folder.id
        legacy_document_id = legacy_document.id
    finally:
        db.close()

    migrate_legacy_trading_research()
    migrate_legacy_trading_research()

    db = core_db.SessionLocal()
    try:
        assert db.query(TradingResearchFolder).filter_by(legacy_notebook_id=legacy_folder_id).count() == 1
        migrated = db.query(TradingResearchDocument).filter_by(legacy_note_id=legacy_document_id).one()
        assert migrated.title == "旧研究内容"
        assert migrated.content == "<p>需要迁移</p>"
        assert db.query(Notebook).filter_by(id=legacy_folder_id).one().module_scope == "trading_migrated"

        db.delete(migrated.folder)
        db.commit()
    finally:
        db.close()

    migrate_legacy_trading_research()

    db = core_db.SessionLocal()
    try:
        assert db.query(TradingResearchFolder).filter_by(legacy_notebook_id=legacy_folder_id).count() == 0
        assert db.query(TradingResearchDocument).filter_by(legacy_note_id=legacy_document_id).count() == 0
    finally:
        db.close()


def test_trading_research_documents_can_be_reordered_and_moved(admin_login):
    client = admin_login
    source_id = client.post("/api/trades/research/folders", json={"name": "排序来源"}).json()["id"]
    target_id = client.post("/api/trades/research/folders", json={"name": "排序目标"}).json()["id"]

    first = client.post(
        "/api/trades/research/documents",
        json={"folder_id": source_id, "title": "第一篇"},
    ).json()
    second = client.post(
        "/api/trades/research/documents",
        json={"folder_id": source_id, "title": "第二篇"},
    ).json()
    target = client.post(
        "/api/trades/research/documents",
        json={"folder_id": target_id, "title": "目标篇"},
    ).json()

    reordered = client.post(
        "/api/trades/research/documents/reorder",
        json={
            "document_id": second["id"],
            "target_folder_id": source_id,
            "target_document_id": first["id"],
            "placement": "before",
        },
    )
    assert reordered.status_code == 200

    source_listing = client.get(
        "/api/trades/research/documents",
        params={"folder_id": source_id, "order": "manual"},
    )
    assert [row["id"] for row in source_listing.json()["items"]] == [second["id"], first["id"]]

    moved = client.post(
        "/api/trades/research/documents/reorder",
        json={
            "document_id": first["id"],
            "target_folder_id": target_id,
            "target_document_id": target["id"],
            "placement": "after",
        },
    )
    assert moved.status_code == 200
    assert moved.json()["folder_id"] == target_id

    target_listing = client.get(
        "/api/trades/research/documents",
        params={"folder_id": target_id, "order": "manual"},
    )
    assert [row["id"] for row in target_listing.json()["items"]] == [target["id"], first["id"]]


def test_trading_research_folders_can_be_reordered_and_moved(admin_login):
    client = admin_login
    first = client.post("/api/trades/research/folders", json={"name": "一级"}).json()
    second = client.post("/api/trades/research/folders", json={"name": "二级"}).json()
    third = client.post("/api/trades/research/folders", json={"name": "三级"}).json()
    created_ids = {first["id"], second["id"], third["id"]}

    reordered = client.post(
        "/api/trades/research/folders/reorder",
        json={
            "folder_id": third["id"],
            "target_parent_id": None,
            "target_folder_id": first["id"],
            "placement": "before",
        },
    )
    assert reordered.status_code == 200
    roots = [
        row
        for row in client.get("/api/trades/research/folders").json()
        if row["parent_id"] is None and row["id"] in created_ids
    ]
    assert [row["id"] for row in roots] == [third["id"], first["id"], second["id"]]

    moved = client.post(
        "/api/trades/research/folders/reorder",
        json={"folder_id": second["id"], "target_parent_id": first["id"], "placement": "end"},
    )
    assert moved.status_code == 200
    assert moved.json()["parent_id"] == first["id"]

    cycle = client.post(
        "/api/trades/research/folders/reorder",
        json={"folder_id": first["id"], "target_parent_id": second["id"], "placement": "end"},
    )
    assert cycle.status_code == 400

    moved_to_root = client.post(
        "/api/trades/research/folders/reorder",
        json={
            "folder_id": second["id"],
            "target_parent_id": None,
            "target_folder_id": first["id"],
            "placement": "before",
        },
    )
    assert moved_to_root.status_code == 200
    assert moved_to_root.json()["parent_id"] is None
