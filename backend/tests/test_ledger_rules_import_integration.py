import json


def _create_account(client, name):
    r = client.post(
        "/api/ledger/accounts",
        json={"name": name, "account_type": "cash", "currency": "CNY", "initial_balance": 0},
    )
    assert r.status_code == 200
    return r.json()["id"]


def _create_category(client, name):
    r = client.post(
        "/api/ledger/categories",
        json={"name": name, "category_type": "expense", "sort_order": 1, "is_active": True},
    )
    assert r.status_code == 200
    return r.json()["id"]


def _preview(client, csv_text, mapping, apply_rules=True):
    return client.post(
        "/api/ledger/import/preview",
        data={
            "delimiter": ",",
            "encoding": "utf-8",
            "has_header": "true",
            "mapping_json": json.dumps(mapping, ensure_ascii=False),
            "apply_rules": "true" if apply_rules else "false",
            "preview_limit": "100",
        },
        files={"file": ("rules.csv", csv_text.encode("utf-8"), "text/csv")},
    )


def test_ledger_rules_apply_on_import_preview(admin_login):
    client = admin_login
    _create_account(client, "rule-import-a1")
    category_id = _create_category(client, "rule-import-c1")

    rule = client.post(
        "/api/ledger/rules",
        json={
            "name": "导入咖啡自动分类",
            "priority": 10,
            "is_active": True,
            "match_json": {"merchant_contains": "coffee", "transaction_type": "expense"},
            "action_json": {"set_category_id": category_id},
        },
    )
    assert rule.status_code == 200

    csv_text = "date,amount,type,direction,account,merchant\n2026-04-20 09:00:00,25,expense,expense,rule-import-a1,Coffee Bean\n"
    mapping = {
        "occurred_at": "date",
        "amount": "amount",
        "transaction_type": "type",
        "direction": "direction",
        "account_name": "account",
        "merchant": "merchant",
    }

    preview = _preview(client, csv_text, mapping, apply_rules=True)
    assert preview.status_code == 200
    row = preview.json()["preview_rows"][0]
    assert row["status"] == "valid"
    assert row["record"]["category_id"] == category_id
    assert "导入咖啡自动分类" in row["matched_rules"]["names"]


def test_ledger_rules_apply_again_on_import_commit(admin_login):
    client = admin_login
    _create_account(client, "rule-import-a2")
    category_id = _create_category(client, "rule-import-c2")

    rule = client.post(
        "/api/ledger/rules",
        json={
            "name": "commit阶段自动分类",
            "priority": 10,
            "is_active": True,
            "match_json": {"merchant_contains": "tea", "transaction_type": "expense"},
            "action_json": {"set_category_id": category_id},
        },
    )
    assert rule.status_code == 200

    csv_text = "date,amount,type,direction,account,merchant\n2026-04-20 10:00:00,18,expense,expense,rule-import-a2,Tea Shop\n"
    mapping = {
        "occurred_at": "date",
        "amount": "amount",
        "transaction_type": "type",
        "direction": "direction",
        "account_name": "account",
        "merchant": "merchant",
    }

    # 预览阶段关闭规则，此时应无分类并标记为无效
    preview = _preview(client, csv_text, mapping, apply_rules=False)
    assert preview.status_code == 200
    row = preview.json()["preview_rows"][0]
    assert row["status"] == "invalid"

    # commit 阶段再次开启规则，要求后端重新应用并通过校验落库
    commit = client.post(
        "/api/ledger/import/commit",
        json={
            "records": preview.json()["preview_rows"],
            "skip_duplicates": True,
            "skip_invalid": False,
            "apply_rules": True,
        },
    )
    assert commit.status_code == 200
    payload = commit.json()
    assert payload["created_count"] == 1
    assert payload["rule_hit_rows"] == 1

    tx_list = client.get("/api/ledger/transactions", params={"source": "import_csv"})
    assert tx_list.status_code == 200
    matched = [x for x in tx_list.json()["items"] if x.get("merchant") == "Tea Shop"]
    assert matched, "导入记录未写入"
    assert matched[0]["category_id"] == category_id
