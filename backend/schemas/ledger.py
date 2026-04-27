from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class LedgerImportBatchItem(BaseModel):
    id: int
    source_type: str
    file_name: str
    file_hash: str
    status: str
    total_rows: int
    parsed_rows: int
    matched_rows: int
    review_rows: int
    duplicate_rows: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class LedgerImportBatchListResponse(BaseModel):
    items: list[LedgerImportBatchItem]
    total: int


class LedgerImportRowItem(BaseModel):
    id: int
    batch_id: int
    row_index: int
    account_id: Optional[int] = None
    raw_payload_json: dict[str, Any]
    raw_text: Optional[str] = None
    normalized_text: Optional[str] = None
    text_fingerprint: Optional[str] = None
    occurred_at: Optional[datetime] = None
    occurred_bucket: Optional[str] = None
    amount: Optional[float] = None
    direction: Optional[str] = None
    balance: Optional[float] = None
    source_channel: Optional[str] = None
    txn_kind: Optional[str] = None
    scene_candidate: Optional[str] = None
    platform: Optional[str] = None
    merchant_raw: Optional[str] = None
    merchant_normalized: Optional[str] = None
    merchant_id: Optional[int] = None
    category_id: Optional[int] = None
    subcategory_id: Optional[int] = None
    confidence: float

    source_rule_id: Optional[int] = None
    source_confidence: Optional[float] = None
    source_explain: Optional[str] = None

    merchant_rule_id: Optional[int] = None
    merchant_confidence: Optional[float] = None
    merchant_explain: Optional[str] = None

    category_rule_id: Optional[int] = None
    category_confidence: Optional[float] = None
    category_explain: Optional[str] = None

    duplicate_key: Optional[str] = None
    duplicate_type: Optional[str] = None
    duplicate_score: Optional[float] = None
    duplicate_basis_json: dict[str, Any] = Field(default_factory=dict)

    review_status: str
    review_note: Optional[str] = None
    low_confidence_reason: Optional[str] = None
    suggested_candidates_json: list[dict[str, Any]] = Field(default_factory=list)
    execution_trace_json: dict[str, Any] = Field(default_factory=dict)


class LedgerImportRowListResponse(BaseModel):
    items: list[LedgerImportRowItem]
    total: int


class LedgerMerchantCreate(BaseModel):
    canonical_name: str = Field(min_length=1, max_length=200)
    aliases: list[str] = Field(default_factory=list)
    default_category_id: Optional[int] = Field(default=None, ge=1)
    default_subcategory_id: Optional[int] = Field(default=None, ge=1)
    tags: list[str] = Field(default_factory=list)


class LedgerMerchantUpdate(BaseModel):
    canonical_name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    aliases: Optional[list[str]] = None
    default_category_id: Optional[int] = Field(default=None, ge=1)
    default_subcategory_id: Optional[int] = Field(default=None, ge=1)
    tags: Optional[list[str]] = None


class LedgerMerchantItem(BaseModel):
    id: int
    canonical_name: str
    aliases: list[str]
    default_category_id: Optional[int] = None
    default_subcategory_id: Optional[int] = None
    tags: list[str]
    hit_count: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class LedgerMerchantListResponse(BaseModel):
    items: list[LedgerMerchantItem]
    total: int


class LedgerRuleCreate(BaseModel):
    rule_type: str = Field(min_length=1, max_length=40)
    priority: int = Field(default=100, ge=0, le=9999)
    enabled: bool = True
    match_mode: str = Field(default="contains", min_length=1, max_length=20)
    pattern: str = Field(min_length=1, max_length=255)
    source_channel_condition: Optional[str] = Field(default=None, max_length=50)
    platform_condition: Optional[str] = Field(default=None, max_length=50)
    direction_condition: Optional[str] = Field(default=None, max_length=20)
    amount_min: Optional[float] = None
    amount_max: Optional[float] = None
    target_platform: Optional[str] = Field(default=None, max_length=50)
    target_merchant: Optional[str] = Field(default=None, max_length=200)
    target_txn_kind: Optional[str] = Field(default=None, max_length=40)
    target_scene: Optional[str] = Field(default=None, max_length=80)
    target_category_id: Optional[int] = Field(default=None, ge=1)
    target_subcategory_id: Optional[int] = Field(default=None, ge=1)
    explain_text: Optional[str] = Field(default=None, max_length=255)
    confidence_score: float = Field(default=0.7, ge=0.0, le=1.0)


class LedgerRuleUpdate(BaseModel):
    rule_type: Optional[str] = Field(default=None, min_length=1, max_length=40)
    priority: Optional[int] = Field(default=None, ge=0, le=9999)
    enabled: Optional[bool] = None
    match_mode: Optional[str] = Field(default=None, min_length=1, max_length=20)
    pattern: Optional[str] = Field(default=None, min_length=1, max_length=255)
    source_channel_condition: Optional[str] = Field(default=None, max_length=50)
    platform_condition: Optional[str] = Field(default=None, max_length=50)
    direction_condition: Optional[str] = Field(default=None, max_length=20)
    amount_min: Optional[float] = None
    amount_max: Optional[float] = None
    target_platform: Optional[str] = Field(default=None, max_length=50)
    target_merchant: Optional[str] = Field(default=None, max_length=200)
    target_txn_kind: Optional[str] = Field(default=None, max_length=40)
    target_scene: Optional[str] = Field(default=None, max_length=80)
    target_category_id: Optional[int] = Field(default=None, ge=1)
    target_subcategory_id: Optional[int] = Field(default=None, ge=1)
    explain_text: Optional[str] = Field(default=None, max_length=255)
    confidence_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class LedgerRuleItem(BaseModel):
    id: int
    rule_type: str
    priority: int
    enabled: bool
    match_mode: str
    pattern: str
    source_channel_condition: Optional[str] = None
    platform_condition: Optional[str] = None
    direction_condition: Optional[str] = None
    amount_min: Optional[float] = None
    amount_max: Optional[float] = None
    target_platform: Optional[str] = None
    target_merchant: Optional[str] = None
    target_txn_kind: Optional[str] = None
    target_scene: Optional[str] = None
    target_category_id: Optional[int] = None
    target_subcategory_id: Optional[int] = None
    explain_text: Optional[str] = None
    confidence_score: float
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class LedgerRuleListResponse(BaseModel):
    items: list[LedgerRuleItem]
    total: int


class LedgerCommitResponse(BaseModel):
    committed_count: int
    created_count: int
    skipped_count: int
    failed_count: int
    errors: list[dict[str, Any]] = Field(default_factory=list)
    transaction_ids: list[int]


class LedgerReviewBulkCategoryRequest(BaseModel):
    row_ids: list[int] = Field(default_factory=list)
    category_id: int = Field(ge=1)
    subcategory_id: Optional[int] = Field(default=None, ge=1)


class LedgerReviewBulkMerchantRequest(BaseModel):
    row_ids: list[int] = Field(default_factory=list)
    merchant_normalized: str = Field(min_length=1, max_length=200)


class LedgerReviewBulkConfirmRequest(BaseModel):
    row_ids: list[int] = Field(default_factory=list)


class LedgerReviewGenerateRuleRequest(BaseModel):
    row_ids: list[int] = Field(default_factory=list)
    # 兼容旧字段：rule_type，同时支持新交互字段 rule_kind
    rule_type: Optional[str] = Field(default=None, min_length=1, max_length=40)
    rule_kind: Optional[str] = Field(default=None, min_length=1, max_length=40)
    match_text: Optional[str] = Field(default=None, min_length=1, max_length=255)
    target_merchant_name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    target_category_name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    target_subcategory_name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    target_source_channel: Optional[str] = Field(default=None, min_length=1, max_length=50)
    target_platform: Optional[str] = Field(default=None, min_length=1, max_length=50)
    priority: int = Field(default=40, ge=0, le=9999)
    preview_only: bool = False
    reprocess_after_create: bool = True
    reprocess_scope: str = Field(default="unconfirmed", min_length=1, max_length=20)
    apply_scope: str = Field(default="global", min_length=1, max_length=20)
    # 兼容旧字段
    target_category_id: Optional[int] = Field(default=None, ge=1)
    target_subcategory_id: Optional[int] = Field(default=None, ge=1)


class LedgerReviewBulkResponse(BaseModel):
    updated_count: int


class LedgerInsightTopItem(BaseModel):
    key: str
    count: int
    amount_sum: float
    row_ids: list[int] = Field(default_factory=list)


class LedgerReviewInsightsResponse(BaseModel):
    unresolved_merchants_top: list[LedgerInsightTopItem] = Field(default_factory=list)
    unresolved_raw_text_top: list[LedgerInsightTopItem] = Field(default_factory=list)


class LedgerRulePreviewItem(BaseModel):
    row_id: int
    rule_type: str
    pattern: str
    expected_hit_rows: int
    skipped_existing: bool
    apply_scope: str
    source_channel_condition: Optional[str] = None
    platform_condition: Optional[str] = None
    target_merchant: Optional[str] = None
    target_category_id: Optional[int] = None
    target_subcategory_id: Optional[int] = None


class LedgerGeneratedRulesResponse(BaseModel):
    created_rule_ids: list[int]
    skipped_existing_count: int = 0
    preview: list[LedgerRulePreviewItem] = Field(default_factory=list)
    estimated_hit_rows: int = 0
    matched_samples: list[dict[str, Any]] = Field(default_factory=list)
    duplicate_rule_count: int = 0
    conflict_rule_count: int = 0
    created_rule_summaries: list[dict[str, Any]] = Field(default_factory=list)
    reprocess_result: dict[str, Any] = Field(default_factory=dict)
