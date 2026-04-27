from __future__ import annotations

from typing import Literal

SourceType = Literal["wechat", "alipay", "bank_card", "unknown"]

PROFILE_COLUMNS: dict[str, dict[str, list[str]]] = {
    "wechat": {
        "occurred_at": ["交易时间", "交易日期", "时间"],
        "amount": ["金额(元)", "金额", "交易金额", "支出", "收入"],
        "direction": ["收/支", "收支类型"],
        "merchant": ["商户名称", "交易对方", "收/付款方", "商户"],
        "raw_text": ["商品", "交易摘要", "备注"],
        "source_channel": ["支付方式", "交易来源", "账单来源"],
        "platform": ["交易状态", "支付方式", "交易渠道"],
        "account_id": ["银行卡号", "账户", "账号"],
        "balance": ["当前状态", "余额"],
    },
    "alipay": {
        "occurred_at": ["交易创建时间", "交易时间", "付款时间"],
        "amount": ["金额", "交易金额(元)", "支出（元）", "收入（元）"],
        "direction": ["收/支", "类型", "交易类型"],
        "merchant": ["交易对方", "对方账户", "商品名称"],
        "raw_text": ["商品说明", "备注", "商品"],
        "source_channel": ["资金状态", "收/付款方式", "交易来源"],
        "platform": ["交易渠道", "支付方式", "来源"],
        "account_id": ["账号", "账户", "银行卡号"],
        "balance": ["账户余额", "余额"],
    },
    "bank_card": {
        "occurred_at": ["交易时间", "交易日期", "日期"],
        "amount": ["交易金额", "金额", "支出", "收入"],
        "direction": ["借贷标志", "收支类型", "方向", "摘要"],
        "merchant": ["交易地点/附言"],
        "raw_text": ["交易地点/附言", "摘要", "交易摘要", "备注", "附言"],
        "source_channel": ["渠道", "交易渠道", "来源"],
        "platform": ["渠道", "交易渠道", "终端"],
        "account_id": ["账号", "卡号", "账户"],
        "balance": ["余额", "账户余额"],
    },
    "unknown": {},
}


def detect_source_type(file_name: str, sample_text: str) -> SourceType:
    name = (file_name or "").lower()
    sample = (sample_text or "").lower()

    if "微信" in file_name or "wechat" in name or "财付通" in sample or "微信支付" in sample:
        return "wechat"
    if "支付宝" in file_name or "alipay" in name or "alipay" in sample:
        return "alipay"
    if any(x in name for x in ("bank", "银行", "icbc", "cmb", "abc", "boc", "card")):
        return "bank_card"
    if any(x in sample for x in ("银行卡", "借贷标志", "交易对手")):
        return "bank_card"
    return "unknown"


def profile_candidates(source_type: str, field_name: str) -> list[str]:
    return (PROFILE_COLUMNS.get(source_type) or {}).get(field_name, [])


def detect_source_type_by_columns(file_name: str, columns: list[str]) -> SourceType:
    normalized_cols = [str(x or "").strip() for x in columns]
    lower_cols = [x.lower() for x in normalized_cols]
    lower_set = set(lower_cols)

    if any(x in lower_set for x in {"交易地点/附言", "对方账号与户名", "借贷标志", "账户余额"}):
        return "bank_card"
    if any(x in lower_set for x in {"收/支", "商品", "商户名称", "交易对方"}) or any("微信" in x or "财付通" in x for x in normalized_cols):
        return "wechat"
    if any(x in lower_set for x in {"交易创建时间", "商品说明", "对方账户"}) or any("支付宝" in x for x in normalized_cols):
        return "alipay"
    return detect_source_type(file_name, "")
