from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Any

from services.ledger.imports.profiles import profile_candidates


DATE_PATTERNS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y/%m/%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y/%m/%d %H:%M",
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y%m%d",
)


def normalize_text(text: Any) -> str:
    raw = str(text or "").strip()
    raw = re.sub(r"\s+", " ", raw)
    return raw


def parse_datetime(value: Any) -> datetime | None:
    text = normalize_text(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        pass
    for fmt in DATE_PATTERNS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def parse_amount(value: Any) -> float | None:
    text = normalize_text(value)
    if not text:
        return None
    text = text.replace(",", "")
    text = text.replace("¥", "").replace("￥", "")
    try:
        return abs(float(text))
    except ValueError:
        return None


def infer_direction(amount_raw: Any, direction_raw: Any) -> str:
    explicit = normalize_text(direction_raw).lower()
    if explicit in {"income", "in", "收入", "+", "贷"}:
        return "income"
    if explicit in {"expense", "out", "支出", "-", "借"}:
        return "expense"

    text = normalize_text(amount_raw)
    if text.startswith("-"):
        return "expense"
    return "income"


def _parse_account_id(value: Any) -> int | None:
    text = normalize_text(value)
    if not text:
        return None
    digits = re.sub(r"\D", "", text)
    if not digits:
        return None
    if len(digits) >= 4:
        return int(digits[-4:])
    return int(digits)


def pick_first(row: dict[str, Any], candidates: list[str]) -> Any:
    for key in candidates:
        if key in row and str(row.get(key) or "").strip() != "":
            return row.get(key)
    return None


def _pick_with_profile(row: dict[str, Any], source_type: str, field: str, fallback: list[str]) -> Any:
    return pick_first(row, profile_candidates(source_type, field) + fallback)


def _pick_first_with_key(row: dict[str, Any], candidates: list[str]) -> tuple[str | None, Any]:
    for key in candidates:
        if key in row and str(row.get(key) or "").strip() != "":
            return key, row.get(key)
    return None, None


def _pick_with_profile_key(row: dict[str, Any], source_type: str, field: str, fallback: list[str]) -> tuple[str | None, Any]:
    return _pick_first_with_key(row, profile_candidates(source_type, field) + fallback)


def _unique_non_empty_parts(parts: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for part in parts:
        val = normalize_text(part)
        if not val:
            continue
        sig = val.lower()
        if sig in seen:
            continue
        seen.add(sig)
        out.append(val)
    return out


def _extract_from_location_text(text: str) -> dict[str, Any]:
    raw = normalize_text(text)
    if not raw:
        return {}

    patterns: list[tuple[str, str, str, str, bool]] = [
        (r"^财付通-微信支付-(.+)$", "wechat", "wechat_pay", "财付通-微信支付-", False),
        (r"^微信支付-(.+)$", "wechat", "wechat_pay", "微信支付-", False),
        (r"^支付宝-支付宝外部商户-(.+)$", "alipay", "alipay", "支付宝-支付宝外部商户-", False),
        (r"^支付宝-(.+)$", "alipay", "alipay", "支付宝-", False),
        (r"^美团支付-(.+)$", "meituan", "meituan_pay", "美团支付-", True),
        (r"^美团App(.+)$", "meituan", "meituan", "美团App", True),
        (r"^美团-(.+)$", "meituan", "meituan", "美团-", True),
    ]
    for regex, source_channel, platform, prefix, keep_parentheses in patterns:
        m = re.match(regex, raw)
        if not m:
            continue
        merchant = _cleanup_merchant_token(m.group(1), keep_parentheses=keep_parentheses)
        return {
            "source_channel": source_channel,
            "platform": platform,
            "merchant_raw": merchant or raw,
            "matched_pattern": prefix,
            "explain": f"命中前缀 {prefix}",
        }
    return {}


def build_text_fingerprint(text: str) -> str:
    lowered = normalize_text(text).lower()
    lowered = re.sub(r"\d+", "#", lowered)
    lowered = re.sub(r"[^\w\u4e00-\u9fff#]+", " ", lowered)
    lowered = normalize_text(lowered)
    return hashlib.sha1(lowered.encode("utf-8")).hexdigest()[:40]


def _cleanup_merchant_token(value: Any, *, keep_parentheses: bool = False) -> str:
    merchant = normalize_text(value)
    if not merchant:
        return ""
    merchant = re.sub(r"^[\\-—_:：]+", "", merchant).strip()
    merchant = re.sub(r"^(美团App|美团支付|美团)-?", "", merchant).strip()
    # 微信/支付宝场景去除括号地址；美团场景保留门店名括号信息。
    if not keep_parentheses:
        merchant = re.sub(r"[（(].*?[)）]", "", merchant).strip()
    # 去除“消费/缴费”等尾部动作词
    merchant = re.sub(r"\b(消费|缴费|支付|付款|转账|还款|退款)\b.*$", "", merchant).strip()
    # 去除尾部账号掩码/卡号等噪声
    merchant = re.sub(r"(?:[A-Za-z0-9*]{3,}[/*]+[A-Za-z0-9*]*)+$", "", merchant).strip()
    merchant = re.sub(r"\s{2,}", " ", merchant).strip()
    merchant = normalize_text(merchant)
    return merchant


def _pick_bank_location_key(row: dict[str, Any]) -> tuple[str | None, Any]:
    return _pick_first_with_key(row, ["交易地点/附言", "交易地点", "附言"])


def normalize_row_payload(row: dict[str, Any], source_type: str) -> tuple[dict[str, Any], dict[str, Any]]:
    occurred_key, occurred_raw = _pick_with_profile_key(
        row,
        source_type,
        "occurred_at",
        ["occurred_at", "交易时间", "交易日期", "时间", "date", "datetime"],
    )
    occurred_at = parse_datetime(occurred_raw)
    if occurred_at:
        # 导入口径统一到“年月日”，不保留时分秒。
        occurred_at = occurred_at.replace(hour=0, minute=0, second=0, microsecond=0)

    amount_key, amount_raw = _pick_with_profile_key(
        row,
        source_type,
        "amount",
        ["amount", "金额", "交易金额", "支出", "收入", "money"],
    )
    amount = parse_amount(amount_raw)

    direction_key, direction_raw = _pick_with_profile_key(
        row,
        source_type,
        "direction",
        ["direction", "收支类型", "类型", "摘要"],
    )
    direction = infer_direction(amount_raw, direction_raw)

    if source_type == "bank_card":
        merchant_key, merchant_val = _pick_bank_location_key(row)
    else:
        merchant_key, merchant_val = _pick_with_profile_key(
            row,
            source_type,
            "merchant",
            ["merchant", "商户", "交易对方", "收/付款方", "商品", "门店", "交易地点/附言"],
        )
    merchant_raw = _cleanup_merchant_token(merchant_val)

    platform_key, platform_val = _pick_with_profile_key(
        row,
        source_type,
        "platform",
        ["platform", "交易渠道", "支付方式", "channel", "source"],
    )
    platform = normalize_text(platform_val)

    source_key, source_val = _pick_with_profile_key(
        row,
        source_type,
        "source_channel",
        ["source_channel", "交易来源", "账单来源", "来源", "source"],
    )
    source_channel = normalize_text(source_val)

    balance_key, balance_val = _pick_with_profile_key(
        row,
        source_type,
        "balance",
        ["balance", "账户余额", "余额"],
    )
    balance = parse_amount(balance_val)

    account_key, account_val = _pick_with_profile_key(
        row,
        source_type,
        "account_id",
        ["account_id", "账号", "卡号", "账户"],
    )
    account_id = _parse_account_id(account_val)

    location_text = normalize_text(merchant_val)
    structured_from_location = _extract_from_location_text(location_text or merchant_raw or "")
    if structured_from_location:
        merchant_raw = structured_from_location.get("merchant_raw") or merchant_raw

    summary_key, summary_val = _pick_first_with_key(row, ["摘要", "交易摘要"])
    summary_text = normalize_text(summary_val)

    if source_type == "bank_card" and location_text:
        # 固定列策略：交易地点/附言作为核心识别文本；摘要仅辅助展示。
        raw_text_parts = _unique_non_empty_parts([location_text, summary_text])
        raw_text_used_columns = [x for x in [merchant_key, summary_key] if x]
        raw_text = normalize_text(" ".join(raw_text_parts))
        normalized_text = normalize_text(f"{location_text} {merchant_raw} {platform} {source_channel}")
    else:
        raw_text_fields = profile_candidates(source_type, "raw_text") + [
            "raw_text",
            "摘要",
            "交易摘要",
            "附言",
            "备注",
            "交易地点/附言",
            "交易地点",
            "用途",
            "商户名",
            "商户名称",
        ]
        raw_text_parts = []
        raw_text_used_columns = []
        for key in raw_text_fields:
            if key in row and str(row.get(key) or "").strip() != "":
                raw_text_parts.append(str(row.get(key)))
                raw_text_used_columns.append(key)
        raw_text_used_columns = list(dict.fromkeys(raw_text_used_columns))
        raw_text_parts = _unique_non_empty_parts(raw_text_parts)
        raw_text = normalize_text(" ".join(raw_text_parts))
        normalized_text = normalize_text(f"{raw_text} {merchant_raw} {platform} {source_channel}")
    text_fingerprint = build_text_fingerprint(normalized_text)
    occurred_bucket = occurred_at.strftime("%Y-%m-%d") if occurred_at else None

    normalized = {
        "account_id": account_id,
        "raw_text": raw_text or None,
        "normalized_text": normalized_text or None,
        "text_fingerprint": text_fingerprint,
        "occurred_at": occurred_at,
        "occurred_bucket": occurred_bucket,
        "amount": amount,
        "direction": direction,
        "balance": balance,
        "source_channel": source_channel or None,
        "platform": platform or None,
        "merchant_raw": merchant_raw or None,
    }
    debug = {
        "selected_columns": {
            "occurred_at": occurred_key,
            "amount": amount_key,
            "direction": direction_key,
            "merchant": merchant_key,
            "platform": platform_key,
            "source_channel": source_key,
            "balance": balance_key,
            "account_id": account_key,
            "raw_text_columns": raw_text_used_columns,
        },
        "raw_text_parts": raw_text_parts[:12],
        "structured_extraction": structured_from_location,
    }
    return normalized, debug
