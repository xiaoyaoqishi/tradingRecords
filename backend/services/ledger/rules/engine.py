from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from models import LedgerCategory, LedgerImportRow, LedgerMerchant, LedgerRule
from services.ledger import apply_owner_scope
from services.ledger.rules.builtin_rules_cn import BUILTIN_RULES_CN
from services.ledger.rules.matchers import text_match
from services.ledger.rules.merchant_resolver import resolve_merchant


def _ensure_category(db: Session, owner_role: str, name: str) -> int:
    row = db.query(LedgerCategory).filter(
        LedgerCategory.owner_role == owner_role,
        LedgerCategory.name == name,
        LedgerCategory.is_deleted == False,  # noqa: E712
    ).first()
    if row:
        return int(row.id)
    created = LedgerCategory(name=name, category_type="expense", owner_role=owner_role)
    db.add(created)
    db.flush()
    return int(created.id)


def ensure_builtin_rules(db: Session, owner_role: str) -> None:
    legacy_mt_rule = db.query(LedgerRule).filter(
        LedgerRule.owner_role == owner_role,
        LedgerRule.is_deleted == False,  # noqa: E712
        LedgerRule.rule_type == "merchant",
        LedgerRule.pattern == "美团app",
    ).first()
    if legacy_mt_rule:
        legacy_mt_rule.enabled = False

    for item in BUILTIN_RULES_CN:
        existing = db.query(LedgerRule).filter(
            LedgerRule.owner_role == owner_role,
            LedgerRule.is_deleted == False,  # noqa: E712
            LedgerRule.rule_type == item["rule_type"],
            LedgerRule.pattern == item["pattern"],
        ).first()
        if existing:
            existing.priority = int(item.get("priority", 100))
            existing.enabled = True
            existing.match_mode = item.get("match_mode", "contains")
            existing.source_channel_condition = item.get("source_channel_condition")
            existing.platform_condition = item.get("platform_condition")
            existing.direction_condition = item.get("direction_condition")
            existing.amount_min = item.get("amount_min")
            existing.amount_max = item.get("amount_max")
            existing.target_platform = item.get("target_platform")
            existing.target_merchant = item.get("target_merchant")
            existing.target_txn_kind = item.get("target_txn_kind")
            existing.target_scene = item.get("target_scene")
            existing.explain_text = item.get("explain_text")
            existing.confidence_score = float(item.get("confidence_score", 0.7))
            continue
        db.add(
            LedgerRule(
                rule_type=item["rule_type"],
                priority=int(item.get("priority", 100)),
                enabled=True,
                match_mode=item.get("match_mode", "contains"),
                pattern=item["pattern"],
                source_channel_condition=item.get("source_channel_condition"),
                platform_condition=item.get("platform_condition"),
                direction_condition=item.get("direction_condition"),
                amount_min=item.get("amount_min"),
                amount_max=item.get("amount_max"),
                target_platform=item.get("target_platform"),
                target_merchant=item.get("target_merchant"),
                target_txn_kind=item.get("target_txn_kind"),
                target_scene=item.get("target_scene"),
                explain_text=item.get("explain_text"),
                confidence_score=float(item.get("confidence_score", 0.7)),
                owner_role=owner_role,
            )
        )
    db.flush()


def _load_rules(db: Session, role: str, owner_role: str, rule_type: str) -> list[LedgerRule]:
    q = db.query(LedgerRule).filter(
        LedgerRule.rule_type == rule_type,
        LedgerRule.is_deleted == False,  # noqa: E712
        LedgerRule.enabled == True,  # noqa: E712
    )
    q = apply_owner_scope(q, LedgerRule, role, owner_role=owner_role)
    return q.order_by(LedgerRule.priority.asc(), LedgerRule.id.asc()).all()


def _load_merchants(db: Session, role: str, owner_role: str) -> list[LedgerMerchant]:
    q = db.query(LedgerMerchant).filter(LedgerMerchant.is_deleted == False)  # noqa: E712
    q = apply_owner_scope(q, LedgerMerchant, role, owner_role=owner_role)
    return q.order_by(LedgerMerchant.hit_count.desc(), LedgerMerchant.id.asc()).all()


def _rule_match(rule: LedgerRule, row: LedgerImportRow, text: str) -> bool:
    if rule.source_channel_condition and (row.source_channel or "") != rule.source_channel_condition:
        return False
    if rule.platform_condition and (row.platform or "") != rule.platform_condition:
        return False
    if rule.direction_condition and (row.direction or "") != rule.direction_condition:
        return False
    if rule.amount_min is not None and (row.amount is None or row.amount < float(rule.amount_min)):
        return False
    if rule.amount_max is not None and (row.amount is None or row.amount > float(rule.amount_max)):
        return False
    return text_match(rule.match_mode, rule.pattern, text)


def _scene_to_category_id(db: Session, owner_role: str, scene: str | None) -> int | None:
    if not scene:
        return None
    mapping = {
        "购物": "购物",
        "餐饮": "餐饮",
        "交通": "交通",
        "转账": "转账",
        "房租": "房租",
        "公共交通": "公共交通",
        "出行": "出行",
        "买菜/商超": "买菜/商超",
        "公用事业": "公用事业",
        "便利店": "便利店",
        "医疗候选": "医疗候选",
        "线下其他待确认": "线下其他待确认",
    }
    name = mapping.get(scene, scene)
    return _ensure_category(db, owner_role, name)


def _apply_source_layer(row: LedgerImportRow, rules: list[LedgerRule], text: str, trace: dict[str, Any]) -> None:
    if "转账" in (text or ""):
        if "财付通" in text or "微信支付" in text:
            row.source_channel = "wechat"
            row.platform = "wechat"
        elif "支付宝" in text:
            row.source_channel = "alipay"
            row.platform = "alipay"
        row.txn_kind = "transfer"
        row.scene_candidate = "transfer"
        row.source_confidence = 0.95
        row.source_explain = "硬规则：文本含转账，统一识别为转账"
        trace["source"] = {
            "matched": True,
            "rule_id": None,
            "pattern": "转账",
            "confidence": row.source_confidence,
            "explain": row.source_explain,
        }
        return

    matched: LedgerRule | None = None
    for rule in rules:
        if _rule_match(rule, row, text):
            matched = rule
            break

    if not matched:
        trace["source"] = {"matched": False, "explain": "未命中来源规则"}
        if not row.source_channel:
            row.source_channel = "unknown"
        if not row.txn_kind:
            row.txn_kind = "expense" if row.direction == "expense" else "income"
        if not row.scene_candidate:
            row.scene_candidate = "unknown"
        row.source_confidence = 0.3
        row.source_explain = "未命中来源规则，按默认方向推断"
        return

    if matched.target_platform:
        row.source_channel = matched.target_platform
    # 用户要求：来源与平台保持同体系（微信/支付宝/美团/京东）。
    if matched.target_platform:
        row.platform = matched.target_platform
    if matched.target_txn_kind:
        row.txn_kind = matched.target_txn_kind
    if matched.target_scene:
        row.scene_candidate = matched.target_scene
    row.source_rule_id = matched.id
    row.source_confidence = float(matched.confidence_score or 0.7)
    row.source_explain = matched.explain_text or f"命中来源规则: {matched.pattern}"
    trace["source"] = {
        "matched": True,
        "rule_id": matched.id,
        "pattern": matched.pattern,
        "confidence": row.source_confidence,
        "explain": row.source_explain,
    }


def _apply_merchant_layer(
    row: LedgerImportRow,
    rules: list[LedgerRule],
    merchants: list[LedgerMerchant],
    text: str,
    trace: dict[str, Any],
) -> None:
    dict_name = resolve_merchant(row.merchant_raw or row.raw_text, merchants)
    dict_merchant = None
    if dict_name:
        for m in merchants:
            if m.canonical_name == dict_name:
                dict_merchant = m
                break

    matched: LedgerRule | None = None
    for rule in rules:
        if _rule_match(rule, row, text):
            matched = rule
            break

    if matched and matched.target_merchant:
        row.merchant_normalized = matched.target_merchant
        row.merchant_rule_id = matched.id
        row.merchant_confidence = float(matched.confidence_score or 0.7)
        row.merchant_explain = matched.explain_text or f"命中商户归一规则: {matched.pattern}"
        trace["merchant"] = {
            "matched": True,
            "rule_id": matched.id,
            "pattern": matched.pattern,
            "merchant_normalized": row.merchant_normalized,
            "confidence": row.merchant_confidence,
            "explain": row.merchant_explain,
        }
        return

    if dict_name:
        row.merchant_normalized = dict_name
        row.merchant_id = dict_merchant.id if dict_merchant else None
        row.merchant_confidence = 0.82 if dict_merchant else 0.74
        row.merchant_explain = "命中商户词典"
        trace["merchant"] = {
            "matched": True,
            "rule_id": None,
            "merchant_id": row.merchant_id,
            "merchant_normalized": row.merchant_normalized,
            "confidence": row.merchant_confidence,
            "explain": row.merchant_explain,
        }
    else:
        fallback = (row.merchant_raw or row.raw_text or "").strip()
        row.merchant_normalized = fallback or None
        row.merchant_confidence = 0.4
        row.merchant_explain = "未命中商户规则，保留原始商户"
        trace["merchant"] = {
            "matched": False,
            "merchant_normalized": row.merchant_normalized,
            "confidence": row.merchant_confidence,
            "explain": row.merchant_explain,
        }


def _apply_category_layer(row: LedgerImportRow, rules: list[LedgerRule], text: str, db: Session, owner_role: str, trace: dict[str, Any]) -> None:
    if (row.txn_kind or "") == "transfer":
        row.category_id = _scene_to_category_id(db, owner_role, "转账")
        row.category_confidence = 0.96
        row.category_explain = "交易类型为转账，统一归类转账"
        trace["category"] = {"matched": True, "rule_id": None, "confidence": 0.96, "explain": row.category_explain}
        return

    # boundary: 美团支付 + 单车优先交通; 美团支付 + 买药候选医疗
    lowered = text.lower()
    if "美团" in lowered and "单车" in lowered:
        row.category_id = _scene_to_category_id(db, owner_role, "交通")
        row.category_confidence = 0.95
        row.category_explain = "边界规则：美团+单车优先归交通"
        trace["category"] = {"matched": True, "rule_id": None, "confidence": 0.95, "explain": row.category_explain}
        return
    if "美团" in lowered and "买药" in lowered:
        row.category_id = _scene_to_category_id(db, owner_role, "医疗候选")
        row.category_confidence = 0.72
        row.category_explain = "边界规则：美团+买药标记医疗候选"
        trace["category"] = {"matched": True, "rule_id": None, "confidence": 0.72, "explain": row.category_explain}
        return
    if "美团支付-美团app" in lowered:
        row.category_id = _scene_to_category_id(db, owner_role, "餐饮")
        row.category_confidence = 0.9
        row.category_explain = "结构规则：美团支付-美团App门店默认归餐饮"
        trace["category"] = {"matched": True, "rule_id": None, "confidence": 0.9, "explain": row.category_explain}
        return

    matched: LedgerRule | None = None
    for rule in rules:
        if _rule_match(rule, row, text):
            matched = rule
            break

    if matched:
        if matched.target_category_id:
            row.category_id = matched.target_category_id
        elif matched.target_scene:
            row.category_id = _scene_to_category_id(db, owner_role, matched.target_scene)
        if matched.target_subcategory_id:
            row.subcategory_id = matched.target_subcategory_id
        row.category_rule_id = matched.id
        row.category_confidence = float(matched.confidence_score or 0.7)
        row.category_explain = matched.explain_text or f"命中分类规则: {matched.pattern}"
        trace["category"] = {
            "matched": True,
            "rule_id": matched.id,
            "pattern": matched.pattern,
            "category_id": row.category_id,
            "confidence": row.category_confidence,
            "explain": row.category_explain,
        }
        return

    # 微信支付 + 普通店名：进入线下其他待确认
    if (row.source_channel or "") == "wechat" and not row.category_id:
        row.category_id = _scene_to_category_id(db, owner_role, "线下其他待确认")
        row.category_confidence = 0.45
        row.category_explain = "微信支付普通店名未命中字典，进入线下其他待确认"
        trace["category"] = {
            "matched": False,
            "fallback": True,
            "category_id": row.category_id,
            "confidence": row.category_confidence,
            "explain": row.category_explain,
        }
        return

    row.category_confidence = 0.0
    row.category_explain = "未命中分类规则"
    trace["category"] = {"matched": False, "confidence": 0.0, "explain": row.category_explain}


def _fallback(row: LedgerImportRow, trace: dict[str, Any]) -> None:
    confidence_values = [x for x in [row.source_confidence, row.merchant_confidence, row.category_confidence] if x is not None]
    row.confidence = round(sum(confidence_values) / len(confidence_values), 4) if confidence_values else 0.0

    candidates: list[dict[str, Any]] = []
    if row.category_id is None:
        candidates.append({"type": "category", "suggest": "餐饮", "score": 0.35})
        candidates.append({"type": "category", "suggest": "购物", "score": 0.32})

    if row.confidence < 0.7 or row.category_id is None:
        row.review_status = "pending"
        row.low_confidence_reason = "规则命中不足或分类置信度低"
    else:
        row.review_status = "pending"
        row.low_confidence_reason = None

    row.suggested_candidates_json = json.dumps(candidates, ensure_ascii=False)
    trace["fallback"] = {
        "review_status": row.review_status,
        "low_confidence_reason": row.low_confidence_reason,
        "suggested_candidates": candidates,
    }
    row.execution_trace_json = json.dumps(trace, ensure_ascii=False)


def classify_rows(db: Session, role: str, owner_role: str, rows: list[LedgerImportRow]) -> dict[str, int]:
    ensure_builtin_rules(db, owner_role)
    source_rules = _load_rules(db, role, owner_role, "source")
    merchant_rules = _load_rules(db, role, owner_role, "merchant")
    category_rules = _load_rules(db, role, owner_role, "category")
    merchants = _load_merchants(db, role, owner_role)

    matched_rows = 0
    review_rows = 0

    for row in rows:
        trace: dict[str, Any] = {}
        try:
            existing_trace = json.loads(row.execution_trace_json or "{}")
        except Exception:
            existing_trace = {}
        if isinstance(existing_trace, dict) and existing_trace.get("parse"):
            trace["parse"] = existing_trace.get("parse")
        text = (row.normalized_text or row.raw_text or "").strip()

        _apply_source_layer(row, source_rules, text, trace)
        _apply_merchant_layer(row, merchant_rules, merchants, text, trace)
        _apply_category_layer(row, category_rules, text, db, owner_role, trace)
        _fallback(row, trace)

        if row.category_id is not None and (row.category_confidence or 0) >= 0.7:
            matched_rows += 1
        else:
            review_rows += 1

    return {"matched_rows": matched_rows, "review_rows": review_rows}


def rule_to_item(row: LedgerRule) -> dict[str, Any]:
    return {
        "id": row.id,
        "rule_type": row.rule_type,
        "priority": row.priority,
        "enabled": bool(row.enabled),
        "match_mode": row.match_mode,
        "pattern": row.pattern,
        "source_channel_condition": row.source_channel_condition,
        "platform_condition": row.platform_condition,
        "direction_condition": row.direction_condition,
        "amount_min": row.amount_min,
        "amount_max": row.amount_max,
        "target_platform": row.target_platform,
        "target_merchant": row.target_merchant,
        "target_txn_kind": row.target_txn_kind,
        "target_scene": row.target_scene,
        "target_category_id": row.target_category_id,
        "target_subcategory_id": row.target_subcategory_id,
        "explain_text": row.explain_text,
        "confidence_score": float(row.confidence_score or 0.0),
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }
