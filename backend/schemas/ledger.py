from datetime import date, datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator


class LedgerAccountType(str, Enum):
    cash = "cash"
    bank = "bank"
    credit_card = "credit_card"
    ewallet = "ewallet"
    investment = "investment"
    other = "other"


class LedgerCategoryType(str, Enum):
    income = "income"
    expense = "expense"
    both = "both"


class LedgerDirection(str, Enum):
    income = "income"
    expense = "expense"
    neutral = "neutral"


class LedgerTransactionType(str, Enum):
    income = "income"
    expense = "expense"
    transfer = "transfer"
    refund = "refund"
    repayment = "repayment"
    fee = "fee"
    interest = "interest"
    adjustment = "adjustment"


class LedgerAccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    account_type: LedgerAccountType
    currency: str = Field(default="CNY", min_length=1, max_length=10)
    initial_balance: float = 0
    is_active: bool = True
    notes: Optional[str] = None


class LedgerAccountUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    account_type: Optional[LedgerAccountType] = None
    currency: Optional[str] = Field(default=None, min_length=1, max_length=10)
    initial_balance: Optional[float] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class LedgerAccountItem(BaseModel):
    id: int
    name: str
    account_type: LedgerAccountType
    currency: str
    initial_balance: float
    current_balance: float
    is_active: bool
    notes: Optional[str] = None
    owner_role: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class LedgerCategoryCreate(BaseModel):
    parent_id: Optional[int] = Field(default=None, ge=1)
    name: str = Field(min_length=1, max_length=120)
    category_type: LedgerCategoryType
    sort_order: int = 0
    is_active: bool = True


class LedgerCategoryUpdate(BaseModel):
    parent_id: Optional[int] = Field(default=None, ge=1)
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    category_type: Optional[LedgerCategoryType] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class LedgerCategoryItem(BaseModel):
    id: int
    parent_id: Optional[int] = None
    name: str
    category_type: LedgerCategoryType
    sort_order: int
    is_active: bool
    owner_role: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class LedgerTransactionCreate(BaseModel):
    occurred_at: datetime
    posted_date: Optional[date] = None
    account_id: int = Field(ge=1)
    counterparty_account_id: Optional[int] = Field(default=None, ge=1)
    category_id: Optional[int] = Field(default=None, ge=1)
    direction: LedgerDirection
    transaction_type: LedgerTransactionType
    amount: float = Field(gt=0)
    currency: str = Field(default="CNY", min_length=1, max_length=10)
    merchant: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = None
    note: Optional[str] = None
    external_ref: Optional[str] = Field(default=None, max_length=120)
    source: str = Field(default="manual", min_length=1, max_length=30)
    linked_transaction_id: Optional[int] = Field(default=None, ge=1)
    is_cleared: bool = False

    @model_validator(mode="after")
    def validate_type_direction(self):
        if self.transaction_type == LedgerTransactionType.transfer:
            if self.direction != LedgerDirection.neutral:
                raise ValueError("transfer direction must be neutral")
        if self.transaction_type == LedgerTransactionType.refund:
            if self.direction != LedgerDirection.income:
                raise ValueError("refund direction must be income")
        return self


class LedgerTransactionUpdate(BaseModel):
    occurred_at: Optional[datetime] = None
    posted_date: Optional[date] = None
    account_id: Optional[int] = Field(default=None, ge=1)
    counterparty_account_id: Optional[int] = Field(default=None, ge=1)
    category_id: Optional[int] = Field(default=None, ge=1)
    direction: Optional[LedgerDirection] = None
    transaction_type: Optional[LedgerTransactionType] = None
    amount: Optional[float] = Field(default=None, gt=0)
    currency: Optional[str] = Field(default=None, min_length=1, max_length=10)
    merchant: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = None
    note: Optional[str] = None
    external_ref: Optional[str] = Field(default=None, max_length=120)
    source: Optional[str] = Field(default=None, min_length=1, max_length=30)
    linked_transaction_id: Optional[int] = Field(default=None, ge=1)
    is_cleared: Optional[bool] = None


class LedgerTransactionItem(BaseModel):
    id: int
    occurred_at: datetime
    posted_date: Optional[date] = None
    account_id: int
    counterparty_account_id: Optional[int] = None
    category_id: Optional[int] = None
    direction: LedgerDirection
    transaction_type: LedgerTransactionType
    amount: float
    currency: str
    merchant: Optional[str] = None
    description: Optional[str] = None
    note: Optional[str] = None
    external_ref: Optional[str] = None
    source: str
    linked_transaction_id: Optional[int] = None
    is_cleared: bool
    owner_role: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class LedgerTransactionListQuery(BaseModel):
    account_id: Optional[int] = Field(default=None, ge=1)
    category_id: Optional[int] = Field(default=None, ge=1)
    transaction_type: Optional[LedgerTransactionType] = None
    direction: Optional[LedgerDirection] = None
    keyword: Optional[str] = None
    source: Optional[str] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None

    @model_validator(mode="after")
    def validate_date_range(self):
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must be <= date_to")
        return self


class LedgerImportPreviewRequest(BaseModel):
    delimiter: str = ","
    encoding: str = "utf-8"
    has_header: bool = True
    mapping: dict[str, str] = Field(default_factory=dict)
    default_account_id: Optional[int] = Field(default=None, ge=1)
    default_currency: str = Field(default="CNY", min_length=1, max_length=10)
    default_transaction_type: Optional[LedgerTransactionType] = None
    default_direction: Optional[LedgerDirection] = None
    apply_rules: bool = True
    preview_limit: int = Field(default=100, ge=1, le=1000)


class LedgerImportPreviewResponse(BaseModel):
    columns: list[str]
    preview_rows: list[dict[str, Any]]
    errors: list[str]
    stats: dict[str, int]


class LedgerImportCommitRequest(BaseModel):
    records: list[dict[str, Any]] = Field(default_factory=list)
    skip_duplicates: bool = True
    skip_invalid: bool = True
    apply_rules: bool = True
    template_id: Optional[int] = Field(default=None, ge=1)


class LedgerImportCommitResponse(BaseModel):
    created_count: int
    skipped_duplicate_count: int
    skipped_invalid_count: int
    failed_count: int
    created_ids: list[int]
    error_rows: list[dict[str, Any]]
    rule_hit_rows: int
    per_rule_hit_summary: dict[str, int]


class LedgerImportTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    delimiter: str = ","
    encoding: str = "utf-8"
    mapping: dict[str, str] = Field(default_factory=dict)
    apply_rules: bool = True


class LedgerImportTemplateItem(BaseModel):
    id: int
    name: str
    delimiter: str
    encoding: str
    mapping: dict[str, str]
    apply_rules: bool = True
    owner_role: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class LedgerRuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    is_active: bool = True
    priority: int = Field(default=100, ge=0, le=9999)
    match_json: dict[str, Any] = Field(default_factory=dict)
    action_json: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_rule(self):
        if not self.match_json:
            raise ValueError("match_json 至少包含一个条件")
        if not self.action_json:
            raise ValueError("action_json 至少包含一个动作")
        return self


class LedgerRuleUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    is_active: Optional[bool] = None
    priority: Optional[int] = Field(default=None, ge=0, le=9999)
    match_json: Optional[dict[str, Any]] = None
    action_json: Optional[dict[str, Any]] = None


class LedgerRuleItem(BaseModel):
    id: int
    name: str
    is_active: bool
    priority: int
    match_json: dict[str, Any]
    action_json: dict[str, Any]
    owner_role: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class LedgerRuleListResponse(BaseModel):
    items: list[LedgerRuleItem]


class LedgerRuleApplyPreviewRequest(BaseModel):
    transaction: Optional[dict[str, Any]] = None
    transaction_ids: list[int] = Field(default_factory=list)
    account_id: Optional[int] = Field(default=None, ge=1)
    category_id: Optional[int] = Field(default=None, ge=1)
    source: Optional[str] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    limit: int = Field(default=20, ge=1, le=200)


class LedgerRuleApplyPreviewResponse(BaseModel):
    items: list[dict[str, Any]]


class LedgerRuleBulkApplyRequest(BaseModel):
    transaction_ids: list[int] = Field(default_factory=list)
    account_id: Optional[int] = Field(default=None, ge=1)
    category_id: Optional[int] = Field(default=None, ge=1)
    source: Optional[str] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None


class LedgerRuleBulkApplyResponse(BaseModel):
    scanned_count: int
    updated_count: int
    skipped_count: int
    error_count: int
    per_rule_hit_summary: dict[str, int]


class LedgerDashboardResponse(BaseModel):
    income_total: float
    expense_total: float
    fee_total: float
    repayment_total: float
    net_cashflow: float
    transaction_count: int
    accounts_summary: list[LedgerAccountItem]
    top_expense_categories: list[dict]
    recent_transactions: list[LedgerTransactionItem]
