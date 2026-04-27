import io


def _post_file(admin_login, filename: str, content: bytes, mime: str):
    files = {"file": (filename, io.BytesIO(content), mime)}
    resp = admin_login.post("/api/ledger/import-batches", files=files)
    assert resp.status_code == 200
    return int(resp.json()["id"])


def _run_to_rows(admin_login, batch_id: int):
    assert admin_login.post(f"/api/ledger/import-batches/{batch_id}/parse").status_code == 200
    assert admin_login.post(f"/api/ledger/import-batches/{batch_id}/classify").status_code == 200
    assert admin_login.post(f"/api/ledger/import-batches/{batch_id}/dedupe").status_code == 200


def test_ledger_analytics_endpoints(admin_login):
    csv_text = """摘要,交易日期,交易金额,账户余额,交易地点/附言
消费,20260123,-6.50,15136.14,财付通-微信支付-三津汤包
消费,20260124,-24.70,14997.18,美团支付-美团App农耕记湖南土菜（南山万科云城店）
消费,20260125,-9.80,14839.38,线下门店测试小店A
"""
    batch_id = _post_file(admin_login, "analytics.csv", csv_text.encode("utf-8"), "text/csv")
    _run_to_rows(admin_login, batch_id)

    rows_resp = admin_login.get(f"/api/ledger/import-batches/{batch_id}/review-rows")
    assert rows_resp.status_code == 200
    row_ids = [int(x["id"]) for x in rows_resp.json()["items"]]

    confirm_resp = admin_login.post(
        f"/api/ledger/import-batches/{batch_id}/review/bulk-confirm",
        json={"row_ids": row_ids},
    )
    assert confirm_resp.status_code == 200

    commit_resp = admin_login.post(f"/api/ledger/import-batches/{batch_id}/commit")
    assert commit_resp.status_code == 200
    assert int(commit_resp.json()["created_count"]) == 3

    params = {"date_from": "2026-01-01", "date_to": "2026-01-31"}

    summary = admin_login.get("/api/ledger/analytics/summary", params=params)
    assert summary.status_code == 200
    summary_payload = summary.json()
    assert summary_payload["交易数"] == 3
    assert summary_payload["总支出"] > 0
    assert "已识别率" in summary_payload

    category = admin_login.get("/api/ledger/analytics/category-breakdown", params=params)
    assert category.status_code == 200
    category_items = category.json()["items"]
    assert isinstance(category_items, list)
    assert all("分类名称" in x and "金额" in x and "占比" in x for x in category_items)

    platform = admin_login.get("/api/ledger/analytics/platform-breakdown", params=params)
    assert platform.status_code == 200
    platform_items = platform.json()["items"]
    labels = {x["平台名称"] for x in platform_items}
    assert {"微信", "支付宝", "美团", "银行卡", "其他"}.issubset(labels)

    top_merchants = admin_login.get("/api/ledger/analytics/top-merchants", params={**params, "limit": 5})
    assert top_merchants.status_code == 200
    top_items = top_merchants.json()["items"]
    assert isinstance(top_items, list)
    assert all("商户名称" in x and "次数" in x and "总金额" in x for x in top_items)

    trend = admin_login.get("/api/ledger/analytics/monthly-trend", params=params)
    assert trend.status_code == 200
    trend_items = trend.json()["items"]
    assert trend_items
    assert all("月份" in x and "总支出" in x and "餐饮" in x and "买菜商超" in x and "交通" in x and "购物" in x for x in trend_items)

    unrecognized = admin_login.get("/api/ledger/analytics/unrecognized-breakdown", params=params)
    assert unrecognized.status_code == 200
    payload = unrecognized.json()
    assert "未识别条数" in payload
    assert "未识别金额占比" in payload
    assert isinstance(payload["未识别商户Top"], list)
    assert isinstance(payload["未识别摘要Top"], list)
