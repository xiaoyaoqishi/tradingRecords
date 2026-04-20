import json
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.orm import Session

from core.errors import AppError
from core.deps import db_session, get_current_role, owner_role_filter_param
from schemas.ledger import (
    LedgerAccountCreate,
    LedgerAccountUpdate,
    LedgerCategoryCreate,
    LedgerCategoryType,
    LedgerCategoryUpdate,
    LedgerImportCommitRequest,
    LedgerRuleApplyPreviewRequest,
    LedgerRuleBulkApplyRequest,
    LedgerRuleCreate,
    LedgerRuleUpdate,
    LedgerImportTemplateCreate,
    LedgerImportPreviewRequest,
    LedgerTransactionCreate,
    LedgerTransactionListQuery,
    LedgerTransactionType,
    LedgerDirection,
    LedgerTransactionUpdate,
)
from services.ledger import account_service, category_service, dashboard_service, import_service, rule_service, transaction_service

router = APIRouter(prefix="/api/ledger", tags=["ledger"])


@router.get("/accounts")
def list_accounts(
    owner_role: Optional[str] = Depends(owner_role_filter_param),
    db: Session = Depends(db_session),
    role: str = Depends(get_current_role),
):
    return account_service.list_accounts(db, role=role, owner_role=owner_role)


@router.post("/accounts")
def create_account(
    payload: LedgerAccountCreate,
    db: Session = Depends(db_session),
    role: str = Depends(get_current_role),
):
    return account_service.create_account(db, payload, role=role)


@router.put("/accounts/{account_id}")
def update_account(
    account_id: int,
    payload: LedgerAccountUpdate,
    db: Session = Depends(db_session),
    role: str = Depends(get_current_role),
):
    return account_service.update_account(db, account_id, payload, role=role)


@router.delete("/accounts/{account_id}")
def delete_account(
    account_id: int,
    db: Session = Depends(db_session),
    role: str = Depends(get_current_role),
):
    return account_service.delete_account(db, account_id, role=role)


@router.get("/categories")
def list_categories(
    category_type: Optional[LedgerCategoryType] = Query(default=None),
    owner_role: Optional[str] = Depends(owner_role_filter_param),
    db: Session = Depends(db_session),
    role: str = Depends(get_current_role),
):
    category_type_value = category_type.value if category_type else None
    return category_service.list_categories(db, role=role, category_type=category_type_value, owner_role=owner_role)


@router.post("/categories")
def create_category(
    payload: LedgerCategoryCreate,
    db: Session = Depends(db_session),
    role: str = Depends(get_current_role),
):
    return category_service.create_category(db, payload, role=role)


@router.put("/categories/{category_id}")
def update_category(
    category_id: int,
    payload: LedgerCategoryUpdate,
    db: Session = Depends(db_session),
    role: str = Depends(get_current_role),
):
    return category_service.update_category(db, category_id, payload, role=role)


@router.delete("/categories/{category_id}")
def delete_category(
    category_id: int,
    db: Session = Depends(db_session),
    role: str = Depends(get_current_role),
):
    return category_service.delete_category(db, category_id, role=role)


@router.get("/transactions")
def list_transactions(
    account_id: Optional[int] = Query(default=None, ge=1),
    category_id: Optional[int] = Query(default=None, ge=1),
    transaction_type: Optional[LedgerTransactionType] = Query(default=None),
    direction: Optional[LedgerDirection] = Query(default=None),
    keyword: Optional[str] = Query(default=None),
    source: Optional[str] = Query(default=None),
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
    owner_role: Optional[str] = Depends(owner_role_filter_param),
    db: Session = Depends(db_session),
    role: str = Depends(get_current_role),
):
    query = LedgerTransactionListQuery(
        account_id=account_id,
        category_id=category_id,
        transaction_type=transaction_type,
        direction=direction,
        keyword=keyword,
        source=source,
        date_from=date_from,
        date_to=date_to,
    )
    return transaction_service.list_transactions(db, role=role, query=query, owner_role=owner_role)


@router.post("/transactions")
def create_transaction(
    payload: LedgerTransactionCreate,
    apply_rules: bool = Query(default=True),
    db: Session = Depends(db_session),
    role: str = Depends(get_current_role),
):
    return transaction_service.create_transaction(db, payload, role=role, apply_rules=apply_rules)


@router.get("/transactions/{transaction_id}")
def get_transaction(
    transaction_id: int,
    db: Session = Depends(db_session),
    role: str = Depends(get_current_role),
):
    return transaction_service.get_transaction(db, transaction_id, role=role)


@router.put("/transactions/{transaction_id}")
def update_transaction(
    transaction_id: int,
    payload: LedgerTransactionUpdate,
    apply_rules: bool = Query(default=True),
    db: Session = Depends(db_session),
    role: str = Depends(get_current_role),
):
    return transaction_service.update_transaction(db, transaction_id, payload, role=role, apply_rules=apply_rules)


@router.delete("/transactions/{transaction_id}")
def delete_transaction(
    transaction_id: int,
    db: Session = Depends(db_session),
    role: str = Depends(get_current_role),
):
    return transaction_service.delete_transaction(db, transaction_id, role=role)


@router.get("/dashboard")
def get_dashboard(
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
    owner_role: Optional[str] = Depends(owner_role_filter_param),
    db: Session = Depends(db_session),
    role: str = Depends(get_current_role),
):
    return dashboard_service.get_dashboard(
        db,
        role=role,
        owner_role=owner_role,
        date_from=date_from,
        date_to=date_to,
    )


@router.post("/import/preview")
def preview_import(
    file: UploadFile = File(...),
    delimiter: str = Form(","),
    encoding: str = Form("utf-8"),
    has_header: bool = Form(True),
    mapping_json: str = Form("{}"),
    default_account_id: Optional[int] = Form(default=None, ge=1),
    default_currency: str = Form("CNY"),
    default_transaction_type: Optional[LedgerTransactionType] = Form(default=None),
    default_direction: Optional[LedgerDirection] = Form(default=None),
    apply_rules: bool = Form(True),
    preview_limit: int = Form(100),
    db: Session = Depends(db_session),
    role: str = Depends(get_current_role),
):
    try:
        mapping = json.loads(mapping_json or "{}")
    except Exception:
        raise AppError("invalid_mapping_json", "mapping_json 必须是合法 JSON", status_code=400)

    payload = LedgerImportPreviewRequest(
        delimiter=delimiter,
        encoding=encoding,
        has_header=has_header,
        mapping=mapping if isinstance(mapping, dict) else {},
        default_account_id=default_account_id,
        default_currency=default_currency,
        default_transaction_type=default_transaction_type,
        default_direction=default_direction,
        apply_rules=apply_rules,
        preview_limit=preview_limit,
    )
    csv_bytes = file.file.read()
    return import_service.preview_import(db, role=role, payload=payload, csv_bytes=csv_bytes)


@router.post("/import/commit")
def commit_import(
    payload: LedgerImportCommitRequest,
    db: Session = Depends(db_session),
    role: str = Depends(get_current_role),
):
    return import_service.commit_import(db, role=role, payload=payload)


@router.get("/import/templates")
def list_import_templates(
    db: Session = Depends(db_session),
    role: str = Depends(get_current_role),
):
    return import_service.list_import_templates(db, role=role)


@router.post("/import/templates")
def create_import_template(
    payload: LedgerImportTemplateCreate,
    db: Session = Depends(db_session),
    role: str = Depends(get_current_role),
):
    return import_service.create_import_template(db, role=role, payload=payload)


@router.delete("/import/templates/{template_id}")
def delete_import_template(
    template_id: int,
    db: Session = Depends(db_session),
    role: str = Depends(get_current_role),
):
    return import_service.delete_import_template(db, role=role, template_id=template_id)


@router.get("/rules")
def list_rules(
    db: Session = Depends(db_session),
    role: str = Depends(get_current_role),
):
    return rule_service.list_rules(db, role=role)


@router.post("/rules")
def create_rule(
    payload: LedgerRuleCreate,
    db: Session = Depends(db_session),
    role: str = Depends(get_current_role),
):
    return rule_service.create_rule(db, role=role, payload=payload)


@router.put("/rules/{rule_id}")
def update_rule(
    rule_id: int,
    payload: LedgerRuleUpdate,
    db: Session = Depends(db_session),
    role: str = Depends(get_current_role),
):
    return rule_service.update_rule(db, role=role, rule_id=rule_id, payload=payload)


@router.delete("/rules/{rule_id}")
def delete_rule(
    rule_id: int,
    db: Session = Depends(db_session),
    role: str = Depends(get_current_role),
):
    return rule_service.delete_rule(db, role=role, rule_id=rule_id)


@router.post("/rules/preview")
def preview_rules(
    payload: LedgerRuleApplyPreviewRequest,
    db: Session = Depends(db_session),
    role: str = Depends(get_current_role),
):
    return rule_service.preview_rules_on_transactions(db, role=role, payload=payload)


@router.post("/rules/reapply")
def reapply_rules(
    payload: LedgerRuleBulkApplyRequest,
    db: Session = Depends(db_session),
    role: str = Depends(get_current_role),
):
    return rule_service.bulk_apply_rules(db, role=role, payload=payload)
