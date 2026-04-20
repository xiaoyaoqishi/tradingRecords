from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from models import LedgerAccount
from services.ledger import apply_owner_scope
from services.ledger.transaction_service import (
    calculate_account_balance_deltas,
    count_transactions,
    list_recent_transactions,
    summarize_income_expense,
    top_expense_categories,
)


def _account_to_summary(account: LedgerAccount, balance_delta: float) -> dict:
    return {
        "id": account.id,
        "name": account.name,
        "account_type": account.account_type,
        "currency": account.currency,
        "initial_balance": float(account.initial_balance or 0),
        "current_balance": float(account.initial_balance or 0) + float(balance_delta),
        "is_active": bool(account.is_active),
        "notes": account.notes,
        "owner_role": account.owner_role,
        "created_at": account.created_at,
        "updated_at": account.updated_at,
    }


def get_dashboard(
    db: Session,
    role: str,
    owner_role: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict:
    totals = summarize_income_expense(db, role=role, owner_role=owner_role, date_from=date_from, date_to=date_to)

    net_cashflow = totals["income_total"] - totals["expense_total"] - totals["fee_total"] - totals["repayment_total"]
    tx_count = count_transactions(db, role=role, owner_role=owner_role, date_from=date_from, date_to=date_to)

    accounts_q = db.query(LedgerAccount).filter(LedgerAccount.is_deleted == False)  # noqa: E712
    accounts_q = apply_owner_scope(accounts_q, LedgerAccount, role, owner_role=owner_role)
    accounts = accounts_q.order_by(LedgerAccount.id.asc()).all()

    deltas = calculate_account_balance_deltas(db, role=role, owner_role=owner_role, date_from=date_from, date_to=date_to)
    account_items = [_account_to_summary(account, deltas.get(account.id, 0.0)) for account in accounts]

    return {
        "income_total": totals["income_total"],
        "expense_total": totals["expense_total"],
        "fee_total": totals["fee_total"],
        "repayment_total": totals["repayment_total"],
        "net_cashflow": net_cashflow,
        "transaction_count": tx_count,
        "accounts_summary": account_items,
        "top_expense_categories": top_expense_categories(
            db,
            role=role,
            owner_role=owner_role,
            date_from=date_from,
            date_to=date_to,
            limit=5,
        ),
        "recent_transactions": list_recent_transactions(
            db,
            role=role,
            owner_role=owner_role,
            date_from=date_from,
            date_to=date_to,
            limit=10,
        ),
    }
