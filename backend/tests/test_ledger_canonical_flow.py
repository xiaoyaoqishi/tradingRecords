import io

from models import LedgerImportBatch, LedgerImportRow, LedgerTransaction


def _post_file(client, filename: str, content: bytes, mime: str = "text/csv") -> int:
    files = {"file": (filename, io.BytesIO(content), mime)}
    resp = client.post("/api/ledger/import-batches", files=files)
    assert resp.status_code == 200
    return int(resp.json()["id"])


def _run_to_reprocess(client, batch_id: int) -> None:
    assert client.post(f"/api/ledger/import-batches/{batch_id}/parse").status_code == 200
    assert client.post(f"/api/ledger/import-batches/{batch_id}/classify").status_code == 200
    assert client.post(f"/api/ledger/import-batches/{batch_id}/reprocess").status_code == 200


def _session():
    import core.db as core_db

    return core_db.SessionLocal()


def test_ledger_router_import_flow_is_live(admin_login):
    listing = admin_login.get("/api/ledger/import-batches")
    assert listing.status_code == 200
    assert "items" in listing.json()


def test_commit_import_batch_only_commits_confirmed_rows_and_is_idempotent(admin_login):
    csv_text = """摘要,交易日期,交易金额,账户余额,交易地点/附言
消费,2026-01-23,-6.50,15136.14,财付通-微信支付-三津汤包
消费,2026-01-24,-15.20,15120.94,财付通-微信支付-罗森便利店
消费,2026-01-25,-30.00,15090.94,财付通-微信支付-朴朴超市
消费,2026-01-26,-40.00,15050.94,财付通-微信支付-滴滴出行
消费,2026-01-27,-50.00,15000.94,财付通-微信支付-京东商城
消费,2026-01-28,-18.00,14982.94,财付通-微信支付-楼下水果店
"""
    batch_id = _post_file(admin_login, "commit-flow.csv", csv_text.encode("utf-8"))
    _run_to_reprocess(admin_login, batch_id)

    rows_resp = admin_login.get(f"/api/ledger/import-batches/{batch_id}/review-rows")
    assert rows_resp.status_code == 200
    rows = rows_resp.json()["items"]
    assert len(rows) == 6

    confirmed_row_ids = [int(rows[0]["id"]), int(rows[5]["id"])]
    confirm_resp = admin_login.post(
        f"/api/ledger/import-batches/{batch_id}/review/bulk-confirm",
        json={"row_ids": confirmed_row_ids},
    )
    assert confirm_resp.status_code == 200
    assert confirm_resp.json()["updated_count"] == 2

    with _session() as db:
        db_rows = db.query(LedgerImportRow).filter(LedgerImportRow.batch_id == batch_id).order_by(LedgerImportRow.row_index.asc()).all()
        db_rows[1].review_status = "ignored"
        db_rows[2].review_status = "pending"
        db_rows[3].review_status = "duplicate"
        db_rows[4].review_status = "rejected"
        db_rows[5].amount = None
        db.commit()

    commit_resp = admin_login.post(f"/api/ledger/import-batches/{batch_id}/commit")
    assert commit_resp.status_code == 200
    payload = commit_resp.json()
    assert payload["committed_count"] == 1
    assert payload["created_count"] == 1
    assert payload["failed_count"] == 1
    assert payload["skipped_count"] == 4
    assert len(payload["errors"]) == 1
    assert payload["errors"][0]["row_id"] == confirmed_row_ids[1]

    with _session() as db:
        txs = db.query(LedgerTransaction).filter(LedgerTransaction.batch_id == batch_id).all()
        assert len(txs) == 1
        tx = txs[0]
        committed_row = db.query(LedgerImportRow).filter(LedgerImportRow.id == confirmed_row_ids[0]).first()
        failed_row = db.query(LedgerImportRow).filter(LedgerImportRow.id == confirmed_row_ids[1]).first()
        assert committed_row is not None and committed_row.review_status == "committed"
        assert failed_row is not None and failed_row.review_status == "invalid"
        assert tx.import_row_id == confirmed_row_ids[0]
        assert tx.batch_id == batch_id
        assert tx.occurred_at is not None
        assert tx.amount == 6.5
        assert tx.direction == "expense"
        assert tx.platform == "wechat"
        assert tx.category_id is not None
        assert tx.description
        assert tx.confidence_score is not None

        tx.merchant_normalized = "三津汤包-人工修正"
        committed_row.review_status = "confirmed"
        committed_row.merchant_normalized = "三津汤包-导入侧再次变化"
        db.commit()

    second_commit = admin_login.post(f"/api/ledger/import-batches/{batch_id}/commit")
    assert second_commit.status_code == 200
    second_payload = second_commit.json()
    assert second_payload["committed_count"] == 0
    assert second_payload["created_count"] == 0
    assert second_payload["failed_count"] == 0
    assert second_payload["skipped_count"] == 6

    with _session() as db:
        txs = db.query(LedgerTransaction).filter(LedgerTransaction.batch_id == batch_id).all()
        assert len(txs) == 1
        assert txs[0].merchant_normalized == "三津汤包-人工修正"


def test_delete_import_batch_rolls_back_committed_transactions(admin_login):
    csv_text = """摘要,交易日期,交易金额,账户余额,交易地点/附言
消费,2026-01-23,-6.50,15136.14,财付通-微信支付-三津汤包
"""
    batch_id = _post_file(admin_login, "delete-batch.csv", csv_text.encode("utf-8"))
    _run_to_reprocess(admin_login, batch_id)

    rows = admin_login.get(f"/api/ledger/import-batches/{batch_id}/review-rows").json()["items"]
    row_ids = [int(rows[0]["id"])]
    confirm_resp = admin_login.post(
        f"/api/ledger/import-batches/{batch_id}/review/bulk-confirm",
        json={"row_ids": row_ids},
    )
    assert confirm_resp.status_code == 200
    commit_resp = admin_login.post(f"/api/ledger/import-batches/{batch_id}/commit")
    assert commit_resp.status_code == 200
    assert commit_resp.json()["created_count"] == 1

    delete_resp = admin_login.delete(f"/api/ledger/import-batches/{batch_id}")
    assert delete_resp.status_code == 200
    assert delete_resp.json()["deleted"] is True
    assert delete_resp.json()["deleted_row_count"] == 1

    with _session() as db:
        assert db.query(LedgerImportBatch).filter(LedgerImportBatch.id == batch_id).first() is None
        assert db.query(LedgerImportRow).filter(LedgerImportRow.batch_id == batch_id).count() == 0
        assert db.query(LedgerTransaction).filter(LedgerTransaction.batch_id == batch_id).count() == 0
