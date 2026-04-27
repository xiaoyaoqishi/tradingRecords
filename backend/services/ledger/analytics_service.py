from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from models import LedgerCategory, LedgerTransaction
from services.ledger import apply_owner_scope, owner_role_for_create

_PLATFORM_LABELS = ["微信", "支付宝", "美团", "银行卡", "其他"]


def _parse_month_key(value: str) -> Optional[date]:
    try:
        return datetime.strptime(value, "%Y-%m").date().replace(day=1)
    except Exception:
        return None


def _month_iter(start: date, end: date) -> list[str]:
    start_month = date(start.year, start.month, 1)
    end_month = date(end.year, end.month, 1)
    out: list[str] = []
    cur = start_month
    while cur <= end_month:
        out.append(cur.strftime("%Y-%m"))
        if cur.month == 12:
            cur = date(cur.year + 1, 1, 1)
        else:
            cur = date(cur.year, cur.month + 1, 1)
    return out


def _tx_query(db: Session, role: str, date_from: Optional[date], date_to: Optional[date]):
    owner_role = owner_role_for_create(role)
    q = db.query(LedgerTransaction).filter(LedgerTransaction.is_deleted == False)  # noqa: E712
    q = apply_owner_scope(q, LedgerTransaction, role, owner_role=owner_role)
    if date_from:
        q = q.filter(func.date(LedgerTransaction.occurred_at) >= date_from)
    if date_to:
        q = q.filter(func.date(LedgerTransaction.occurred_at) <= date_to)
    return q


def _expense_query(db: Session, role: str, date_from: Optional[date], date_to: Optional[date]):
    return _tx_query(db, role, date_from, date_to).filter(LedgerTransaction.direction == "expense")


def _unrecognized_condition():
    return or_(
        LedgerTransaction.category_id.is_(None),
        LedgerTransaction.source_channel.is_(None),
        LedgerTransaction.source_channel == "",
        LedgerTransaction.merchant_normalized.is_(None),
        LedgerTransaction.merchant_normalized == "",
    )


def _platform_label_expr():
    raw = func.lower(func.coalesce(LedgerTransaction.platform, LedgerTransaction.source_channel, ""))
    return case(
        (raw.in_(["wechat", "wechat_pay"]), "微信"),
        (raw.in_(["alipay", "alipay_pay"]), "支付宝"),
        (raw.in_(["meituan", "meituan_pay"]), "美团"),
        (raw.in_(["bank_card", "bank"]), "银行卡"),
        else_="其他",
    )


def get_summary(db: Session, role: str, date_from: Optional[date], date_to: Optional[date]) -> dict[str, Any]:
    q = _tx_query(db, role, date_from, date_to)
    total_count = q.count()

    expense_total = float(
        q.with_entities(func.coalesce(func.sum(case((LedgerTransaction.direction == "expense", LedgerTransaction.amount), else_=0.0)), 0.0)).scalar()
        or 0.0
    )

    recognized_count = q.filter(
        LedgerTransaction.category_id.is_not(None),
        LedgerTransaction.source_channel.is_not(None),
        LedgerTransaction.source_channel != "",
        LedgerTransaction.merchant_normalized.is_not(None),
        LedgerTransaction.merchant_normalized != "",
    ).count()

    unrecognized_q = q.filter(_unrecognized_condition())
    unrecognized_count = unrecognized_q.count()
    unrecognized_amount = float(
        unrecognized_q.with_entities(func.coalesce(func.sum(case((LedgerTransaction.direction == "expense", LedgerTransaction.amount), else_=0.0)), 0.0)).scalar()
        or 0.0
    )

    return {
        "总支出": round(expense_total, 2),
        "交易数": int(total_count),
        "已识别率": round((recognized_count / total_count) if total_count else 0.0, 4),
        "未识别数": int(unrecognized_count),
        "未识别金额": round(unrecognized_amount, 2),
        "未识别金额占比": round((unrecognized_amount / expense_total) if expense_total else 0.0, 4),
    }


def get_category_breakdown(db: Session, role: str, date_from: Optional[date], date_to: Optional[date]) -> dict[str, Any]:
    q = _expense_query(db, role, date_from, date_to)
    rows = (
        q.outerjoin(LedgerCategory, LedgerCategory.id == LedgerTransaction.category_id)
        .with_entities(
            func.coalesce(LedgerCategory.name, "未识别分类").label("分类名称"),
            func.sum(LedgerTransaction.amount).label("金额"),
        )
        .group_by("分类名称")
        .order_by(func.sum(LedgerTransaction.amount).desc())
        .all()
    )

    total = sum(float(x[1] or 0) for x in rows)
    items = [
        {
            "分类名称": str(name),
            "金额": round(float(amount or 0), 2),
            "占比": round(float(amount or 0) / total, 4) if total else 0.0,
        }
        for name, amount in rows
    ]
    return {"items": items, "总支出": round(total, 2)}


def get_platform_breakdown(db: Session, role: str, date_from: Optional[date], date_to: Optional[date]) -> dict[str, Any]:
    q = _expense_query(db, role, date_from, date_to)
    label_expr = _platform_label_expr()
    grouped = (
        q.with_entities(label_expr.label("平台名称"), func.sum(LedgerTransaction.amount).label("金额"))
        .group_by("平台名称")
        .all()
    )
    mapped = {str(name): float(amount or 0) for name, amount in grouped}
    total = sum(mapped.values())
    items = []
    for name in _PLATFORM_LABELS:
        amount = float(mapped.get(name, 0.0))
        items.append({"平台名称": name, "金额": round(amount, 2), "占比": round(amount / total, 4) if total else 0.0})
    return {"items": items, "总支出": round(total, 2)}


def get_top_merchants(db: Session, role: str, date_from: Optional[date], date_to: Optional[date], limit: int = 10) -> dict[str, Any]:
    q = _expense_query(db, role, date_from, date_to)
    merchant_expr = func.coalesce(LedgerTransaction.merchant_normalized, LedgerTransaction.merchant_raw, "未识别商户")
    rows = (
        q.with_entities(
            merchant_expr.label("商户名称"),
            func.count(LedgerTransaction.id).label("次数"),
            func.sum(LedgerTransaction.amount).label("总金额"),
        )
        .group_by("商户名称")
        .order_by(func.sum(LedgerTransaction.amount).desc(), func.count(LedgerTransaction.id).desc())
        .limit(int(limit))
        .all()
    )
    items = [
        {"商户名称": str(name), "次数": int(count or 0), "总金额": round(float(amount or 0), 2)}
        for name, count, amount in rows
    ]
    return {"items": items, "total": len(items)}


def get_monthly_trend(db: Session, role: str, date_from: Optional[date], date_to: Optional[date]) -> dict[str, Any]:
    end_date = date_to or date.today()
    start_date = date_from or date(end_date.year, max(1, end_date.month - 5), 1)

    q = _expense_query(db, role, start_date, end_date)
    month_expr = func.strftime("%Y-%m", LedgerTransaction.occurred_at)

    total_rows = (
        q.with_entities(month_expr.label("月份"), func.sum(LedgerTransaction.amount).label("总支出"))
        .group_by("月份")
        .all()
    )

    trend_by_month: dict[str, dict[str, float]] = defaultdict(lambda: {"总支出": 0.0, "餐饮": 0.0, "买菜商超": 0.0, "交通": 0.0, "购物": 0.0})
    for month, amount in total_rows:
        if not month:
            continue
        trend_by_month[str(month)]["总支出"] = float(amount or 0)

    cat_rows = (
        q.outerjoin(LedgerCategory, LedgerCategory.id == LedgerTransaction.category_id)
        .with_entities(month_expr.label("月份"), func.coalesce(LedgerCategory.name, "未识别分类").label("分类"), func.sum(LedgerTransaction.amount).label("金额"))
        .group_by("月份", "分类")
        .all()
    )

    for month, category_name, amount in cat_rows:
        if not month:
            continue
        category = str(category_name or "")
        if category in {"餐饮", "买菜/商超", "买菜商超", "交通", "购物"}:
            key = "买菜商超" if category in {"买菜/商超", "买菜商超"} else category
            trend_by_month[str(month)][key] += float(amount or 0)

    month_keys = _month_iter(start_date, end_date)
    items = []
    for month in month_keys:
        base = trend_by_month.get(month, {"总支出": 0.0, "餐饮": 0.0, "买菜商超": 0.0, "交通": 0.0, "购物": 0.0})
        items.append(
            {
                "月份": month,
                "总支出": round(float(base.get("总支出", 0.0)), 2),
                "餐饮": round(float(base.get("餐饮", 0.0)), 2),
                "买菜商超": round(float(base.get("买菜商超", 0.0)), 2),
                "交通": round(float(base.get("交通", 0.0)), 2),
                "购物": round(float(base.get("购物", 0.0)), 2),
            }
        )
    return {"items": items, "date_from": start_date.isoformat(), "date_to": end_date.isoformat()}


def get_unrecognized_breakdown(db: Session, role: str, date_from: Optional[date], date_to: Optional[date]) -> dict[str, Any]:
    base_q = _tx_query(db, role, date_from, date_to)
    expense_total = float(
        base_q.with_entities(func.coalesce(func.sum(case((LedgerTransaction.direction == "expense", LedgerTransaction.amount), else_=0.0)), 0.0)).scalar()
        or 0.0
    )

    q = base_q.filter(_unrecognized_condition())
    unrecognized_count = q.count()
    unrecognized_amount = float(
        q.with_entities(func.coalesce(func.sum(case((LedgerTransaction.direction == "expense", LedgerTransaction.amount), else_=0.0)), 0.0)).scalar()
        or 0.0
    )

    merchant_expr = func.coalesce(LedgerTransaction.merchant_raw, LedgerTransaction.merchant_normalized, "未识别商户")
    merchant_top_rows = (
        q.filter(LedgerTransaction.direction == "expense")
        .with_entities(merchant_expr.label("商户"), func.count(LedgerTransaction.id).label("次数"), func.sum(LedgerTransaction.amount).label("金额"))
        .group_by("商户")
        .order_by(func.count(LedgerTransaction.id).desc(), func.sum(LedgerTransaction.amount).desc())
        .limit(10)
        .all()
    )

    text_expr = func.coalesce(LedgerTransaction.description, LedgerTransaction.normalized_text, "无摘要")
    text_top_rows = (
        q.filter(LedgerTransaction.direction == "expense")
        .with_entities(text_expr.label("摘要"), func.count(LedgerTransaction.id).label("次数"), func.sum(LedgerTransaction.amount).label("金额"))
        .group_by("摘要")
        .order_by(func.count(LedgerTransaction.id).desc(), func.sum(LedgerTransaction.amount).desc())
        .limit(10)
        .all()
    )

    return {
        "未识别条数": int(unrecognized_count),
        "未识别金额": round(unrecognized_amount, 2),
        "未识别金额占比": round((unrecognized_amount / expense_total) if expense_total else 0.0, 4),
        "未识别商户Top": [
            {"商户": str(name), "次数": int(count or 0), "金额": round(float(amount or 0), 2)}
            for name, count, amount in merchant_top_rows
        ],
        "未识别摘要Top": [
            {"摘要": str(name), "次数": int(count or 0), "金额": round(float(amount or 0), 2)}
            for name, count, amount in text_top_rows
        ],
    }
