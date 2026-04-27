import io
from pathlib import Path

from models import LedgerImportRow, LedgerTransaction
from services.ledger.imports import pipeline


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


def test_legacy_ledger_services_and_symbols_are_absent():
    ledger_dir = Path(__file__).resolve().parents[1] / "services" / "ledger"
    assert not (ledger_dir / "account_service.py").exists()
    assert not (ledger_dir / "transaction_service.py").exists()
    assert not (ledger_dir / "recurring_service.py").exists()

    banned_tokens = {
        "LedgerAccount",
        "LedgerRecurringRule",
        "account_service",
        "transaction_service",
        "recurring_service",
        "/api/ledger/accounts",
        "/api/ledger/transactions",
        "/api/ledger/recurring",
        "posted_date",
        "counterparty_account_id",
        "linked_transaction_id",
        "transaction_type",
        "is_cleared",
    }
    for path in ledger_dir.rglob("*.py"):
        content = path.read_text(encoding="utf-8")
        for token in banned_tokens:
            assert token not in content, f"{token} leaked into {path}"


def test_repeat_commit_is_idempotent_and_preserves_manual_transaction_fields(admin_login):
    csv_text = """摘要,交易日期,交易金额,账户余额,交易地点/附言
消费,2026-01-23,-6.50,15136.14,财付通-微信支付-三津汤包
"""
    batch_id = _post_file(admin_login, "idempotent-commit.csv", csv_text.encode("utf-8"))
    _run_to_reprocess(admin_login, batch_id)

    rows = admin_login.get(f"/api/ledger/import-batches/{batch_id}/review-rows").json()["items"]
    row_id = int(rows[0]["id"])
    confirm_resp = admin_login.post(
        f"/api/ledger/import-batches/{batch_id}/review/bulk-confirm",
        json={"row_ids": [row_id]},
    )
    assert confirm_resp.status_code == 200
    first_commit = admin_login.post(f"/api/ledger/import-batches/{batch_id}/commit")
    assert first_commit.status_code == 200
    assert first_commit.json()["created_count"] == 1

    with _session() as db:
        tx = db.query(LedgerTransaction).filter(LedgerTransaction.import_row_id == row_id).first()
        row = db.query(LedgerImportRow).filter(LedgerImportRow.id == row_id).first()
        assert tx is not None
        assert row is not None
        tx.category_id = None
        tx.merchant_normalized = "人工修正商户"
        tx.description = "人工修正摘要"
        tx.review_note = "人工修正备注"
        tx.platform = "manual-platform"
        row.review_status = "approved"
        row.amount = None
        row.category_id = 999999
        row.merchant_normalized = "导入侧再次变化"
        row.review_note = "导入侧再次变化"
        row.platform = "wechat"
        db.commit()

    second_commit = admin_login.post(f"/api/ledger/import-batches/{batch_id}/commit")
    assert second_commit.status_code == 200
    payload = second_commit.json()
    assert payload["created_count"] == 0
    assert payload["committed_count"] == 0
    assert payload["failed_count"] == 0
    assert payload["skipped_count"] == 1

    with _session() as db:
        txs = db.query(LedgerTransaction).filter(LedgerTransaction.import_row_id == row_id).all()
        assert len(txs) == 1
        tx = txs[0]
        row = db.query(LedgerImportRow).filter(LedgerImportRow.id == row_id).first()
        assert row is not None and row.review_status == "committed"
        assert tx.category_id is None
        assert tx.merchant_normalized == "人工修正商户"
        assert tx.description == "人工修正摘要"
        assert tx.review_note == "人工修正备注"
        assert tx.platform == "manual-platform"


def test_committed_batch_rejects_reprocessing_mutations(admin_login):
    csv_text = """摘要,交易日期,交易金额,账户余额,交易地点/附言
消费,2026-01-23,-6.50,15136.14,财付通-微信支付-三津汤包
"""
    batch_id = _post_file(admin_login, "committed-guard.csv", csv_text.encode("utf-8"))
    _run_to_reprocess(admin_login, batch_id)

    rows = admin_login.get(f"/api/ledger/import-batches/{batch_id}/review-rows").json()["items"]
    row_id = int(rows[0]["id"])
    confirm_resp = admin_login.post(
        f"/api/ledger/import-batches/{batch_id}/review/bulk-confirm",
        json={"row_ids": [row_id]},
    )
    assert confirm_resp.status_code == 200
    commit_resp = admin_login.post(f"/api/ledger/import-batches/{batch_id}/commit")
    assert commit_resp.status_code == 200
    assert commit_resp.json()["created_count"] == 1

    blocked_calls = [
        ("post", f"/api/ledger/import-batches/{batch_id}/parse", None),
        ("post", f"/api/ledger/import-batches/{batch_id}/classify", None),
        ("post", f"/api/ledger/import-batches/{batch_id}/dedupe", None),
        ("post", f"/api/ledger/import-batches/{batch_id}/reprocess", None),
        ("post", f"/api/ledger/import-batches/{batch_id}/review/bulk-category", {"row_ids": [row_id], "category_id": 1}),
        ("post", f"/api/ledger/import-batches/{batch_id}/review/bulk-merchant", {"row_ids": [row_id], "merchant_normalized": "人工商户"}),
        ("post", f"/api/ledger/import-batches/{batch_id}/review/bulk-confirm", {"row_ids": [row_id]}),
        ("post", f"/api/ledger/import-batches/{batch_id}/review/reclassify-pending", None),
        (
            "post",
            f"/api/ledger/import-batches/{batch_id}/review/generate-rule",
            {"row_ids": [row_id], "rule_type": "merchant", "priority": 33, "preview_only": False, "reprocess_after_create": True},
        ),
    ]
    for method, path, payload in blocked_calls:
        response = getattr(admin_login, method)(path, json=payload) if payload is not None else getattr(admin_login, method)(path)
        assert response.status_code == 409, (path, response.status_code, response.text)
        assert "该批次已入账" in response.text


def test_review_generate_rule_unconfirmed_scope_only_reprocesses_pending(admin_login, monkeypatch):
    csv_text = """摘要,交易日期,交易金额,账户余额,交易地点/附言
消费,2026-01-23,-6.50,15136.14,财付通-微信支付-三津汤包
消费,2026-01-24,-7.50,15128.64,财付通-微信支付-罗森便利店
消费,2026-01-25,-8.50,15120.14,财付通-微信支付-朴朴超市
消费,2026-01-26,-9.50,15110.64,财付通-微信支付-滴滴出行
消费,2026-01-27,-10.50,15100.14,财付通-微信支付-京东商城
消费,2026-01-28,-11.50,15088.64,财付通-微信支付-楼下水果店
消费,2026-01-29,-12.50,15076.14,财付通-微信支付-便利蜂
消费,2026-01-30,-13.50,15062.64,财付通-微信支付-盒马鲜生
"""
    batch_id = _post_file(admin_login, "rule-scope.csv", csv_text.encode("utf-8"))
    _run_to_reprocess(admin_login, batch_id)

    rows = admin_login.get(f"/api/ledger/import-batches/{batch_id}/review-rows").json()["items"]
    row_ids = [int(item["id"]) for item in rows]
    status_map = {
        row_ids[0]: "pending",
        row_ids[1]: "approved",
        row_ids[2]: "accepted",
        row_ids[3]: "committed",
        row_ids[4]: "ignored",
        row_ids[5]: "rejected",
        row_ids[6]: "duplicate",
        row_ids[7]: "invalid",
    }

    with _session() as db:
        db_rows = db.query(LedgerImportRow).filter(LedgerImportRow.batch_id == batch_id).order_by(LedgerImportRow.row_index.asc()).all()
        for row in db_rows:
            row.review_status = status_map[int(row.id)]
        db.commit()

    captured = {}

    def fake_classify_rows(_db, _role, _owner_role, replay_rows):
        captured["row_ids"] = [int(row.id) for row in replay_rows]
        captured["statuses"] = [str(row.review_status) for row in replay_rows]
        return {"matched_rows": 0, "review_rows": len(replay_rows)}

    monkeypatch.setattr(pipeline, "classify_rows", fake_classify_rows)

    response = admin_login.post(
        f"/api/ledger/import-batches/{batch_id}/review/generate-rule",
        json={
            "row_ids": [row_ids[0]],
            "rule_type": "merchant",
            "match_text": "状态过滤测试唯一关键词",
            "target_merchant_name": "状态过滤测试商户",
            "priority": 33,
            "preview_only": False,
            "reprocess_after_create": True,
            "reprocess_scope": "unconfirmed",
        },
    )
    assert response.status_code == 200
    assert captured["row_ids"] == [row_ids[0]]
    assert captured["statuses"] == ["pending"]
