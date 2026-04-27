import io
import zipfile
from xml.sax.saxutils import escape

from services.ledger.imports.normalizers import normalize_row_payload


def _post_file(admin_login, filename: str, content: bytes, mime: str):
    files = {"file": (filename, io.BytesIO(content), mime)}
    resp = admin_login.post("/api/ledger/import-batches", files=files)
    assert resp.status_code == 200
    return resp.json()["id"]


def _run_to_dedupe(admin_login, batch_id: int):
    assert admin_login.post(f"/api/ledger/import-batches/{batch_id}/parse").status_code == 200
    assert admin_login.post(f"/api/ledger/import-batches/{batch_id}/classify").status_code == 200
    assert admin_login.post(f"/api/ledger/import-batches/{batch_id}/dedupe").status_code == 200


def _col(n: int) -> str:
    out = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        out = chr(65 + r) + out
    return out


def _build_xlsx(headers: list[str], data_rows: list[list[str]]) -> bytes:
    strings: list[str] = []
    string_map: dict[str, int] = {}

    def sidx(value: str) -> int:
        if value not in string_map:
            string_map[value] = len(strings)
            strings.append(value)
        return string_map[value]

    all_rows = [headers] + data_rows
    row_xml = []
    for r_idx, row in enumerate(all_rows, start=1):
        cells = []
        for c_idx, value in enumerate(row, start=1):
            idx = sidx(str(value))
            ref = f"{_col(c_idx)}{r_idx}"
            cells.append(f'<c r="{ref}" t="s"><v>{idx}</v></c>')
        row_xml.append(f'<row r="{r_idx}">{"".join(cells)}</row>')

    shared_items = "".join([f"<si><t>{escape(v)}</t></si>" for v in strings])

    content_types = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">
  <Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/>
  <Default Extension=\"xml\" ContentType=\"application/xml\"/>
  <Override PartName=\"/xl/workbook.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml\"/>
  <Override PartName=\"/xl/worksheets/sheet1.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml\"/>
  <Override PartName=\"/xl/sharedStrings.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml\"/>
</Types>"""

    rels = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">
  <Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"xl/workbook.xml\"/>
</Relationships>"""

    workbook = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<workbook xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\" xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\">
  <sheets>
    <sheet name=\"Sheet1\" sheetId=\"1\" r:id=\"rId1\"/>
  </sheets>
</workbook>"""

    workbook_rels = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">
  <Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet\" Target=\"worksheets/sheet1.xml\"/>
  <Relationship Id=\"rId2\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings\" Target=\"sharedStrings.xml\"/>
</Relationships>"""

    sheet1 = f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<worksheet xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\">
  <sheetData>{''.join(row_xml)}</sheetData>
</worksheet>"""

    shared = f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<sst xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\" count=\"{len(strings)}\" uniqueCount=\"{len(strings)}\">{shared_items}</sst>"""

    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("xl/workbook.xml", workbook)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        zf.writestr("xl/worksheets/sheet1.xml", sheet1)
        zf.writestr("xl/sharedStrings.xml", shared)
    return out.getvalue()


def test_phase2_layered_rules_dedupe_and_review_closure(admin_login):
    csv_text = """交易时间,金额,交易摘要,商户,交易渠道,交易来源
2026-04-01 08:30:00,8,微信支付深圳通充值,微信支付深圳通,微信支付,微信账单
2026-04-01 09:00:00,120,京东订单,京东商城,微信支付,微信账单
2026-04-01 09:30:00,2.5,美团支付 单车骑行,美团支付,微信支付,微信账单
2026-04-01 10:00:00,15,微信支付 小王五金店,小王五金店,微信支付,微信账单
2026-04-01 10:00:00,15,微信支付 小王五金店,小王五金店,微信支付,微信账单
"""
    batch_id = _post_file(admin_login, "wechat.csv", csv_text.encode("utf-8"), "text/csv")
    _run_to_dedupe(admin_login, batch_id)

    review_resp = admin_login.get(f"/api/ledger/import-batches/{batch_id}/review-rows")
    assert review_resp.status_code == 200
    rows = review_resp.json()["items"]
    assert len(rows) == 5

    shenzhen = next(x for x in rows if "深圳通" in (x.get("normalized_text") or ""))
    assert shenzhen["source_channel"] == "wechat"
    assert "公共交通" in (shenzhen.get("category_explain") or "")

    jd = next(x for x in rows if "京东" in (x.get("normalized_text") or ""))
    assert "购物" in (jd.get("category_explain") or "")

    bike = next(x for x in rows if "单车" in (x.get("normalized_text") or ""))
    assert "交通" in (bike.get("category_explain") or "")
    assert "餐饮" not in (bike.get("category_explain") or "")

    hardware = next(x for x in rows if "五金店" in (x.get("normalized_text") or "") and x.get("duplicate_type") is None)
    assert hardware["review_status"] == "pending"
    assert "待确认" in ((hardware.get("category_explain") or "") + (hardware.get("low_confidence_reason") or ""))

    assert all(x.get("duplicate_type") is None for x in rows)

    row_ids = [hardware["id"]]
    r1 = admin_login.post(
        f"/api/ledger/import-batches/{batch_id}/review/bulk-merchant",
        json={"row_ids": row_ids, "merchant_normalized": "小王五金店"},
    )
    assert r1.status_code == 200 and r1.json()["updated_count"] == 1

    # use existing category from 京东 row
    r2 = admin_login.post(
        f"/api/ledger/import-batches/{batch_id}/review/bulk-category",
        json={"row_ids": row_ids, "category_id": jd["category_id"]},
    )
    assert r2.status_code == 200 and r2.json()["updated_count"] == 1

    r3 = admin_login.post(
        f"/api/ledger/import-batches/{batch_id}/review/generate-rule",
        json={"row_ids": row_ids, "rule_type": "merchant", "priority": 33},
    )
    assert r3.status_code == 200
    assert len(r3.json()["created_rule_ids"]) >= 1

    r4 = admin_login.post(
        f"/api/ledger/import-batches/{batch_id}/review/bulk-confirm",
        json={"row_ids": row_ids},
    )
    assert r4.status_code == 200 and r4.json()["updated_count"] == 1

    commit_resp = admin_login.post(f"/api/ledger/import-batches/{batch_id}/commit")
    assert commit_resp.status_code == 200
    committed = commit_resp.json()
    assert committed["created_count"] == 1
    assert committed["skipped_count"] >= 4


def test_wechat_convenience_keywords_and_transfer_category(admin_login):
    csv_text = """摘要,交易日期,交易金额,账户余额,交易地点/附言
消费,20260123,-12.30,15136.14,财付通-微信支付-小区百货商店
转账,20260123,-50.00,15086.14,财付通-微信支付-微信转账
"""
    files = {"file": ("bank.csv", io.BytesIO(csv_text.encode("utf-8")), "text/csv")}
    create_resp = admin_login.post("/api/ledger/import-batches", files=files)
    batch_id = create_resp.json()["id"]
    _run_to_dedupe(admin_login, batch_id)

    rows = admin_login.get(f"/api/ledger/import-batches/{batch_id}/review-rows").json()["items"]
    assert len(rows) == 2

    store = next(x for x in rows if "百货商店" in (x.get("raw_text") or ""))
    assert store["source_channel"] == "wechat"
    assert store["category_name"] == "便利店"

    transfer = next(x for x in rows if "微信转账" in (x.get("raw_text") or ""))
    assert transfer["txn_kind"] == "transfer"
    assert transfer["category_name"] == "转账"


def test_phase2_xlsx_import_pipeline(admin_login):
    xlsx_bytes = _build_xlsx(
        ["交易时间", "金额", "交易摘要", "商户", "交易渠道", "交易来源"],
        [["2026-04-02 12:00:00", "20", "京东买书", "京东", "微信支付", "微信账单"]],
    )
    batch_id = _post_file(admin_login, "wechat.xlsx", xlsx_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    _run_to_dedupe(admin_login, batch_id)

    rows = admin_login.get(f"/api/ledger/import-batches/{batch_id}/review-rows").json()["items"]
    assert len(rows) == 1
    assert "京东" in (rows[0].get("merchant_normalized") or rows[0].get("normalized_text") or "")


def test_phase2_xls_html_import_pipeline(admin_login):
    html_xls = """<html><body><table>
<tr><th>交易时间</th><th>金额</th><th>交易摘要</th><th>商户</th><th>交易渠道</th><th>交易来源</th></tr>
<tr><td>2026-04-03 08:00:00</td><td>18</td><td>美团外卖早餐</td><td>美团外卖</td><td>微信支付</td><td>微信账单</td></tr>
</table></body></html>""".encode("utf-8")
    batch_id = _post_file(admin_login, "bank-export.xls", html_xls, "application/vnd.ms-excel")
    _run_to_dedupe(admin_login, batch_id)

    rows = admin_login.get(f"/api/ledger/import-batches/{batch_id}/review-rows").json()["items"]
    assert len(rows) == 1
    assert "餐饮" in (rows[0].get("category_explain") or "")


def test_reprocess_runs_full_trace_chain(admin_login):
    csv_text = """摘要,交易日期,交易金额,账户余额,交易地点/附言
消费,20260123,-6.50,15136.14,财付通-微信支付-三津汤包
"""
    files = {"file": ("bank.csv", io.BytesIO(csv_text.encode("utf-8")), "text/csv")}
    create_resp = admin_login.post("/api/ledger/import-batches", files=files)
    batch_id = create_resp.json()["id"]

    assert admin_login.post(f"/api/ledger/import-batches/{batch_id}/parse").status_code == 200
    rows_before = admin_login.get(f"/api/ledger/import-batches/{batch_id}/review-rows").json()["items"]
    assert rows_before and list((rows_before[0].get("execution_trace_json") or {}).keys()) == ["parse"]

    reprocess_resp = admin_login.post(f"/api/ledger/import-batches/{batch_id}/reprocess")
    assert reprocess_resp.status_code == 200

    rows_after = admin_login.get(f"/api/ledger/import-batches/{batch_id}/review-rows").json()["items"]
    assert rows_after
    trace_keys = set((rows_after[0].get("execution_trace_json") or {}).keys())
    assert {"parse", "source", "merchant", "category", "fallback"}.issubset(trace_keys)
    assert rows_after[0]["source_channel"] == "wechat"
    assert rows_after[0]["platform"] == "wechat"
    assert rows_after[0]["merchant_normalized"] == "三津汤包"
    assert rows_after[0]["category_name"] == "餐饮"


def test_delete_import_batch(admin_login):
    csv_text = """摘要,交易日期,交易金额,账户余额,交易地点/附言
消费,20260123,-6.50,15136.14,财付通-微信支付-三津汤包
"""
    files = {"file": ("bank.csv", io.BytesIO(csv_text.encode("utf-8")), "text/csv")}
    create_resp = admin_login.post("/api/ledger/import-batches", files=files)
    batch_id = create_resp.json()["id"]

    assert admin_login.post(f"/api/ledger/import-batches/{batch_id}/parse").status_code == 200
    del_resp = admin_login.delete(f"/api/ledger/import-batches/{batch_id}")
    assert del_resp.status_code == 200
    assert del_resp.json().get("deleted") is True

    list_payload = admin_login.get("/api/ledger/import-batches").json()
    assert all(x["id"] != batch_id for x in list_payload["items"])

    missing = admin_login.get(f"/api/ledger/import-batches/{batch_id}/review-rows")
    assert missing.status_code == 404


def test_bank_profile_raw_text_composition_and_recognition(admin_login):
    row = {
        "序号": "1",
        "摘要": "消费",
        "交易日期": "20260123",
        "交易金额": "-6.50",
        "账户余额": "15,136.14",
        "交易地点/附言": "财付通-微信支付-三津汤包",
        "对方账号与户名": "4******9202/**汤包",
    }
    normalized, debug = normalize_row_payload(row, "bank_card")
    assert normalized["raw_text"] and "财付通-微信支付-三津汤包" in normalized["raw_text"]
    assert "消费" in normalized["raw_text"]
    assert "4******9202/**汤包" not in normalized["normalized_text"]
    assert normalized["source_channel"] is None
    assert normalized["platform"] is None
    assert normalized["merchant_raw"] == "三津汤包"
    assert debug["selected_columns"]["raw_text_columns"]
    assert debug["structured_extraction"]["matched_pattern"] == "财付通-微信支付-"

    alipay_row = {
        "摘要": "消费",
        "交易日期": "20260123",
        "交易金额": "-93.26",
        "账户余额": "15021.88",
        "交易地点/附言": "支付宝-支付宝外部商户-福州朴朴电子商务有限公司",
        "对方账号与户名": "Z******0010/***公司",
    }
    normalized_alipay, _ = normalize_row_payload(alipay_row, "bank_card")
    assert normalized_alipay["source_channel"] is None
    assert normalized_alipay["platform"] is None
    assert normalized_alipay["merchant_raw"] == "福州朴朴电子商务有限公司"

    meituan_row = {
        "摘要": "消费",
        "交易日期": "20260124",
        "交易金额": "-24.70",
        "账户余额": "14997.18",
        "交易地点/附言": "美团支付-美团App农耕记湖南土菜（南山万科云城店）",
    }
    normalized_mt, _ = normalize_row_payload(meituan_row, "bank_card")
    assert normalized_mt["merchant_raw"] == "农耕记湖南土菜（南山万科云城店）"

    csv_text = """摘要,交易日期,交易金额,账户余额,交易地点/附言,对方账号与户名
消费,20260123,-6.50,15136.14,财付通-微信支付-三津汤包,4******9202/**汤包
"""
    files = {"file": ("bank.csv", io.BytesIO(csv_text.encode("utf-8")), "text/csv")}
    create_resp = admin_login.post("/api/ledger/import-batches", files=files)
    batch_id = create_resp.json()["id"]
    assert admin_login.post(f"/api/ledger/import-batches/{batch_id}/parse").status_code == 200
    assert admin_login.post(f"/api/ledger/import-batches/{batch_id}/classify").status_code == 200
    payload = admin_login.get(f"/api/ledger/import-batches/{batch_id}/review-rows").json()
    assert payload["total"] == 1
    item = payload["items"][0]
    assert item["raw_text"] and "三津汤包" in item["raw_text"]
    assert item["merchant_normalized"]
    assert item["source_channel"] == "wechat"
    assert item["platform"] == "wechat"

    mt_csv = """摘要,交易日期,交易金额,账户余额,交易地点/附言
消费,20260124,-24.70,14997.18,美团支付-美团App农耕记湖南土菜（南山万科云城店）
"""
    mt_resp = admin_login.post("/api/ledger/import-batches", files={"file": ("bank2.csv", io.BytesIO(mt_csv.encode("utf-8")), "text/csv")})
    mt_id = mt_resp.json()["id"]
    assert admin_login.post(f"/api/ledger/import-batches/{mt_id}/parse").status_code == 200
    assert admin_login.post(f"/api/ledger/import-batches/{mt_id}/reprocess").status_code == 200
    mt_item = admin_login.get(f"/api/ledger/import-batches/{mt_id}/review-rows").json()["items"][0]
    assert mt_item["merchant_raw"] == "农耕记湖南土菜（南山万科云城店）"
    assert mt_item["merchant_normalized"] == "农耕记"
    assert mt_item["category_name"] == "餐饮"
    assert mt_item["source_channel"] == "meituan"
    assert mt_item["platform"] == "meituan"

    mixed_csv = """摘要,交易日期,交易金额,账户余额,交易地点/附言
消费,20260125,-99.00,14898.18,京东支付-京东商城-美的京东自营旗舰店
消费,20260125,-22.00,14876.18,财付通-微信支付-太原爱瑞云餐饮
消费,20260125,-16.00,14860.18,美团支付-美团App杨记胡辣汤牛肉面（太原店）
消费,20260125,-35.00,14825.18,拼多多支付-拼多多平台商户
"""
    mixed_resp = admin_login.post("/api/ledger/import-batches", files={"file": ("bank3.csv", io.BytesIO(mixed_csv.encode("utf-8")), "text/csv")})
    mixed_id = mixed_resp.json()["id"]
    assert admin_login.post(f"/api/ledger/import-batches/{mixed_id}/parse").status_code == 200
    assert admin_login.post(f"/api/ledger/import-batches/{mixed_id}/reprocess").status_code == 200
    mixed_rows = admin_login.get(f"/api/ledger/import-batches/{mixed_id}/review-rows").json()["items"]

    jd = next(x for x in mixed_rows if "京东商城" in (x.get("raw_text") or ""))
    assert jd["source_channel"] == "jd"
    assert jd["platform"] == "jd"

    wx = next(x for x in mixed_rows if "爱瑞云餐饮" in (x.get("raw_text") or ""))
    assert wx["source_channel"] == "wechat"
    assert wx["platform"] == "wechat"

    mt = next(x for x in mixed_rows if "杨记胡辣汤牛肉面" in (x.get("raw_text") or ""))
    assert mt["source_channel"] == "meituan"
    assert mt["platform"] == "meituan"

    pdd = next(x for x in mixed_rows if "京东商城" not in (x.get("raw_text") or "") and "拼多多" in (x.get("raw_text") or ""))
    assert pdd["source_channel"] == "pinduoduo"
    assert pdd["platform"] == "pinduoduo"

    kw_csv = """摘要,交易日期,交易金额,账户余额,交易地点/附言
消费,20260125,-11.00,14849.18,财付通-微信支付-鑫海公寓
消费,20260125,-9.80,14839.38,财付通-微信支付-易站便利
消费,20260125,-18.00,14821.38,财付通-微信支付-老王小吃
"""
    kw_resp = admin_login.post("/api/ledger/import-batches", files={"file": ("bank4.csv", io.BytesIO(kw_csv.encode("utf-8")), "text/csv")})
    kw_id = kw_resp.json()["id"]
    assert admin_login.post(f"/api/ledger/import-batches/{kw_id}/parse").status_code == 200
    assert admin_login.post(f"/api/ledger/import-batches/{kw_id}/reprocess").status_code == 200
    kw_rows = admin_login.get(f"/api/ledger/import-batches/{kw_id}/review-rows").json()["items"]

    rent = next(x for x in kw_rows if "鑫海公寓" in (x.get("raw_text") or ""))
    assert rent["category_name"] == "房租"
    store = next(x for x in kw_rows if "易站便利" in (x.get("raw_text") or ""))
    assert store["category_name"] == "便利店"
    food = next(x for x in kw_rows if "老王小吃" in (x.get("raw_text") or ""))
    assert food["category_name"] == "餐饮"


def test_rules_crud_management(admin_login):
    create_resp = admin_login.post(
        "/api/ledger/rules",
        json={
            "rule_type": "category",
            "priority": 77,
            "enabled": True,
            "match_mode": "contains",
            "pattern": "测试规则商户",
            "target_scene": "餐饮",
            "explain_text": "测试规则",
            "confidence_score": 0.88,
        },
    )
    assert create_resp.status_code == 200
    rule_id = create_resp.json()["id"]

    update_resp = admin_login.put(
        f"/api/ledger/rules/{rule_id}",
        json={"priority": 55, "enabled": False, "target_scene": "便利店", "explain_text": "已编辑"},
    )
    assert update_resp.status_code == 200
    updated = update_resp.json()
    assert updated["priority"] == 55
    assert updated["enabled"] is False
    assert updated["target_scene"] == "便利店"

    delete_resp = admin_login.delete(f"/api/ledger/rules/{rule_id}")
    assert delete_resp.status_code == 200
    assert delete_resp.json()["deleted"] is True

    list_resp = admin_login.get("/api/ledger/rules")
    assert list_resp.status_code == 200
    ids = [x["id"] for x in list_resp.json()["items"]]
    assert rule_id not in ids


def test_review_insights_and_generate_rule_preview(admin_login):
    csv_text = """摘要,交易日期,交易金额,账户余额,交易地点/附言
消费,20260123,-8.80,1000.00,线下门店测试小店A
消费,20260123,-12.20,987.80,线下门店测试小店A
消费,20260123,-9.90,977.90,线下门店测试小店B
"""
    batch_id = _post_file(admin_login, "insight.csv", csv_text.encode("utf-8"), "text/csv")
    _run_to_dedupe(admin_login, batch_id)

    rows_resp = admin_login.get(f"/api/ledger/import-batches/{batch_id}/review-rows")
    assert rows_resp.status_code == 200
    rows = rows_resp.json()["items"]
    target = next(x for x in rows if "测试小店A" in (x.get("merchant_raw") or ""))

    insight_resp = admin_login.get(f"/api/ledger/import-batches/{batch_id}/review-insights")
    assert insight_resp.status_code == 200
    insights = insight_resp.json()
    assert insights["unresolved_merchants_top"]
    assert insights["unresolved_merchants_top"][0]["count"] >= 1
    assert "amount_sum" in insights["unresolved_merchants_top"][0]

    preview_resp = admin_login.post(
        f"/api/ledger/import-batches/{batch_id}/review/generate-rule",
        json={
            "row_ids": [target["id"]],
            "rule_kind": "merchant",
            "match_text": target.get("merchant_raw") or "测试小店A",
            "target_merchant_name": "测试小店A",
            "priority": 35,
            "preview_only": True,
            "apply_scope": "profile",
        },
    )
    assert preview_resp.status_code == 200
    preview_payload = preview_resp.json()
    assert preview_payload["created_rule_ids"] == []
    assert preview_payload["preview"]
    assert preview_payload["preview"][0]["expected_hit_rows"] >= 1
    assert preview_payload["estimated_hit_rows"] >= 1

    create_resp = admin_login.post(
        f"/api/ledger/import-batches/{batch_id}/review/generate-rule",
        json={
            "row_ids": [target["id"]],
            "rule_kind": "merchant",
            "match_text": target.get("merchant_raw") or "测试小店A",
            "target_merchant_name": "测试小店A",
            "priority": 35,
            "preview_only": False,
            "apply_scope": "profile",
            "reprocess_after_create": True,
        },
    )
    assert create_resp.status_code == 200
    created = create_resp.json()
    assert len(created["created_rule_ids"]) >= 1

    create_again_resp = admin_login.post(
        f"/api/ledger/import-batches/{batch_id}/review/generate-rule",
        json={
            "row_ids": [target["id"]],
            "rule_kind": "merchant",
            "match_text": target.get("merchant_raw") or "测试小店A",
            "target_merchant_name": "测试小店A",
            "priority": 35,
            "preview_only": False,
            "apply_scope": "profile",
        },
    )
    assert create_again_resp.status_code == 200
    assert create_again_resp.json()["skipped_existing_count"] >= 1


def test_categories_endpoint_returns_tree(admin_login):
    resp = admin_login.get("/api/ledger/categories")
    assert resp.status_code == 200
    payload = resp.json()
    assert isinstance(payload.get("items"), list)
    if payload["items"]:
        assert "children" in payload["items"][0]


def test_generate_source_rule_and_reprocess_scope(admin_login):
    csv_text = """摘要,交易日期,交易金额,账户余额,交易地点/附言
消费,20260123,-18.80,1000.00,支付宝-支付宝外部商户-北京度友科技有限公司 消费
"""
    batch_id = _post_file(admin_login, "source-rule.csv", csv_text.encode("utf-8"), "text/csv")
    _run_to_dedupe(admin_login, batch_id)
    row = admin_login.get(f"/api/ledger/import-batches/{batch_id}/review-rows").json()["items"][0]

    resp = admin_login.post(
        f"/api/ledger/import-batches/{batch_id}/review/generate-rule",
        json={
            "row_ids": [row["id"]],
            "rule_kind": "source",
            "match_text": "北京度友科技有限公司",
            "target_platform": "alipay",
            "priority": 40,
            "preview_only": False,
            "reprocess_after_create": True,
            "reprocess_scope": "all",
        },
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert len(payload.get("created_rule_ids") or []) >= 1
    assert payload.get("reprocess_result", {}).get("reprocess_scope") == "all"


def test_merchant_dictionary_update_with_recent_rows(admin_login):
    csv_text = """摘要,交易日期,交易金额,账户余额,交易地点/附言
消费,20260123,-6.50,15136.14,财付通-微信支付-三津汤包
"""
    batch_id = _post_file(admin_login, "merchant-update.csv", csv_text.encode("utf-8"), "text/csv")
    _run_to_dedupe(admin_login, batch_id)

    create_resp = admin_login.post(
        "/api/ledger/merchants",
        json={"canonical_name": "三津汤包", "aliases": ["三津"], "tags": []},
    )
    assert create_resp.status_code == 200
    merchant_id = create_resp.json()["id"]

    update_resp = admin_login.put(
        f"/api/ledger/merchants/{merchant_id}",
        json={
            "canonical_name": "三津汤包店",
            "aliases": ["三津", "汤包店"],
            "default_category_id": 1,
        },
    )
    assert update_resp.status_code == 200
    updated = update_resp.json()
    assert updated["canonical_name"] == "三津汤包店"
    assert "汤包店" in updated["aliases"]
    assert isinstance(updated.get("recent_rows") or [], list)


def test_review_reclassify_pending(admin_login):
    csv_text = """摘要,交易日期,交易金额,账户余额,交易地点/附言
消费,20260123,-6.50,15136.14,财付通-微信支付-三津汤包
消费,20260123,-9.80,15126.34,线下门店测试小店A
"""
    batch_id = _post_file(admin_login, "reclassify.csv", csv_text.encode("utf-8"), "text/csv")
    _run_to_dedupe(admin_login, batch_id)

    rows_resp = admin_login.get(f"/api/ledger/import-batches/{batch_id}/review-rows")
    assert rows_resp.status_code == 200
    row_ids = [int(x["id"]) for x in rows_resp.json()["items"]]
    assert row_ids

    confirm_resp = admin_login.post(
        f"/api/ledger/import-batches/{batch_id}/review/bulk-confirm",
        json={"row_ids": [row_ids[0]]},
    )
    assert confirm_resp.status_code == 200

    reclassify_resp = admin_login.post(f"/api/ledger/import-batches/{batch_id}/review/reclassify-pending")
    assert reclassify_resp.status_code == 200
    payload = reclassify_resp.json()
    assert payload["reclassified_count"] >= 1


def test_generate_source_rule_with_other_normalizes_target_platform(admin_login):
    csv_text = """摘要,交易日期,交易金额,账户余额,交易地点/附言
消费,20260123,-9.80,14839.38,线下门店测试小店B
"""
    batch_id = _post_file(admin_login, "source-other.csv", csv_text.encode("utf-8"), "text/csv")
    _run_to_dedupe(admin_login, batch_id)

    review_rows = admin_login.get(f"/api/ledger/import-batches/{batch_id}/review-rows").json()["items"]
    assert len(review_rows) == 1
    row = review_rows[0]

    resp = admin_login.post(
        f"/api/ledger/import-batches/{batch_id}/review/generate-rule",
        json={
            "row_ids": [row["id"]],
            "rule_kind": "source",
            "match_text": "线下门店测试小店B",
            "target_platform": "unkonwn",
            "priority": 40,
            "preview_only": False,
            "reprocess_after_create": True,
            "reprocess_scope": "all",
        },
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert len(payload.get("created_rule_ids") or []) >= 1
    created_summary = (payload.get("created_rule_summaries") or [])[0]
    assert created_summary["target_platform"] == "other"

    rows_after = admin_login.get(f"/api/ledger/import-batches/{batch_id}/review-rows").json()["items"]
    assert len(rows_after) == 1
    assert rows_after[0]["source_channel"] == "other"
    assert rows_after[0]["platform"] == "other"
    assert rows_after[0]["source_channel_display"] == "其他"
    assert rows_after[0]["platform_display"] == "其他"


def test_import_occured_at_normalized_to_date_only(admin_login):
    csv_text = """交易时间,金额,交易摘要,商户,交易渠道,交易来源
2026-04-01 08:30:45,8,微信支付深圳通充值,微信支付深圳通,微信支付,微信账单
"""
    batch_id = _post_file(admin_login, "date-only.csv", csv_text.encode("utf-8"), "text/csv")
    _run_to_dedupe(admin_login, batch_id)

    review_resp = admin_login.get(f"/api/ledger/import-batches/{batch_id}/review-rows")
    assert review_resp.status_code == 200
    item = review_resp.json()["items"][0]
    occurred_at = item.get("occurred_at") or ""
    occurred_bucket = item.get("occurred_bucket") or ""
    assert "00:00:00" in occurred_at
    assert occurred_bucket == "2026-04-01"


def test_generate_category_rule_with_target_category_id_for_unrecognized_row(admin_login):
    csv_text = """摘要,交易日期,交易金额,账户余额,交易地点/附言
消费,20260123,-9.80,14839.38,线下门店测试小店A
"""
    batch_id = _post_file(admin_login, "category-target.csv", csv_text.encode("utf-8"), "text/csv")
    _run_to_dedupe(admin_login, batch_id)

    review_rows = admin_login.get(f"/api/ledger/import-batches/{batch_id}/review-rows").json()["items"]
    assert len(review_rows) == 1
    row = review_rows[0]
    assert row.get("category_id") is None

    resp = admin_login.post(
        f"/api/ledger/import-batches/{batch_id}/review/generate-rule",
        json={
            "row_ids": [row["id"]],
            "rule_type": "category",
            "priority": 40,
            "apply_scope": "profile",
            "target_category_id": 1,
        },
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert len(payload.get("created_rule_ids") or []) >= 1
