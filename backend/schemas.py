from pydantic import BaseModel, Field
from typing import Optional, List, Union
from datetime import date, datetime

from trade_review_taxonomy import OpportunityStructure, EdgeSource, FailureType, ReviewConclusion

class TradeCreate(BaseModel):
    trade_date: date
    instrument_type: str
    symbol: str
    contract: Optional[str] = None
    category: Optional[str] = None
    direction: str
    open_time: datetime
    close_time: Optional[datetime] = None
    open_price: float
    close_price: Optional[float] = None
    quantity: float
    margin: Optional[float] = None
    commission: Optional[float] = 0
    slippage: Optional[float] = 0
    pnl: Optional[float] = None
    pnl_points: Optional[float] = None
    holding_duration: Optional[str] = None
    is_overnight: Optional[bool] = False
    trading_session: Optional[str] = None
    status: Optional[str] = "open"

    is_main_contract: Optional[str] = None
    is_near_delivery: Optional[bool] = False
    is_contract_switch: Optional[bool] = False
    is_high_volatility: Optional[bool] = False
    is_near_data_release: Optional[bool] = False

    entry_logic: Optional[str] = None
    exit_logic: Optional[str] = None
    strategy_type: Optional[str] = None
    market_condition: Optional[str] = None
    timeframe: Optional[str] = None
    core_signal: Optional[str] = None
    stop_loss_plan: Optional[float] = None
    target_plan: Optional[float] = None
    followed_plan: Optional[bool] = None

    is_planned: Optional[bool] = None
    is_impulsive: Optional[bool] = False
    is_chasing: Optional[bool] = False
    is_holding_loss: Optional[bool] = False
    is_early_profit: Optional[bool] = False
    is_extended_stop: Optional[bool] = False
    is_overweight: Optional[bool] = False
    is_revenge: Optional[bool] = False
    is_emotional: Optional[bool] = False
    mental_state: Optional[str] = None
    physical_state: Optional[str] = None

    pre_opportunity: Optional[str] = None
    pre_win_reason: Optional[str] = None
    pre_risk: Optional[str] = None
    during_match_expectation: Optional[str] = None
    during_plan_changed: Optional[str] = None
    post_quality: Optional[str] = None
    post_repeat: Optional[bool] = None
    post_root_cause: Optional[str] = None
    post_replicable: Optional[bool] = None

    error_tags: Optional[str] = None
    review_note: Optional[str] = None
    notes: Optional[str] = None
    is_favorite: Optional[bool] = False
    star_rating: Optional[int] = Field(default=None, ge=1, le=5)


class TradeUpdate(BaseModel):
    trade_date: Optional[date] = None
    instrument_type: Optional[str] = None
    symbol: Optional[str] = None
    contract: Optional[str] = None
    category: Optional[str] = None
    direction: Optional[str] = None
    open_time: Optional[datetime] = None
    close_time: Optional[datetime] = None
    open_price: Optional[float] = None
    close_price: Optional[float] = None
    quantity: Optional[float] = None
    margin: Optional[float] = None
    commission: Optional[float] = None
    slippage: Optional[float] = None
    pnl: Optional[float] = None
    pnl_points: Optional[float] = None
    holding_duration: Optional[str] = None
    is_overnight: Optional[bool] = None
    trading_session: Optional[str] = None
    status: Optional[str] = None

    is_main_contract: Optional[str] = None
    is_near_delivery: Optional[bool] = None
    is_contract_switch: Optional[bool] = None
    is_high_volatility: Optional[bool] = None
    is_near_data_release: Optional[bool] = None

    entry_logic: Optional[str] = None
    exit_logic: Optional[str] = None
    strategy_type: Optional[str] = None
    market_condition: Optional[str] = None
    timeframe: Optional[str] = None
    core_signal: Optional[str] = None
    stop_loss_plan: Optional[float] = None
    target_plan: Optional[float] = None
    followed_plan: Optional[bool] = None

    is_planned: Optional[bool] = None
    is_impulsive: Optional[bool] = None
    is_chasing: Optional[bool] = None
    is_holding_loss: Optional[bool] = None
    is_early_profit: Optional[bool] = None
    is_extended_stop: Optional[bool] = None
    is_overweight: Optional[bool] = None
    is_revenge: Optional[bool] = None
    is_emotional: Optional[bool] = None
    mental_state: Optional[str] = None
    physical_state: Optional[str] = None

    pre_opportunity: Optional[str] = None
    pre_win_reason: Optional[str] = None
    pre_risk: Optional[str] = None
    during_match_expectation: Optional[str] = None
    during_plan_changed: Optional[str] = None
    post_quality: Optional[str] = None
    post_repeat: Optional[bool] = None
    post_root_cause: Optional[str] = None
    post_replicable: Optional[bool] = None

    error_tags: Optional[str] = None
    review_note: Optional[str] = None
    notes: Optional[str] = None
    is_favorite: Optional[bool] = None
    star_rating: Optional[int] = Field(default=None, ge=1, le=5)


class TradeResponse(TradeCreate):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    source_broker_name: Optional[str] = None
    source_label: Optional[str] = None
    source_display: Optional[str] = None
    source_is_metadata: Optional[bool] = None
    has_trade_review: Optional[bool] = None

    class Config:
        from_attributes = True


class TradePasteImportRequest(BaseModel):
    raw_text: str
    broker: Optional[str] = None


class TradePasteImportError(BaseModel):
    row: int
    reason: str
    raw: Optional[str] = None


class TradePasteImportResponse(BaseModel):
    inserted: int
    skipped: int
    errors: List[TradePasteImportError] = []


class TradePositionResponse(BaseModel):
    symbol: str
    contract: Optional[str] = None
    net_quantity: float
    side: str
    avg_open_price: float
    open_since: Optional[date] = None
    last_trade_date: Optional[date] = None


class TradeSearchOptionItemResponse(BaseModel):
    trade_id: int
    trade_date: Optional[date] = None
    symbol: Optional[str] = None
    contract: Optional[str] = None
    direction: Optional[str] = None
    quantity: Optional[float] = None
    open_price: Optional[float] = None
    close_price: Optional[float] = None
    status: Optional[str] = None
    pnl: Optional[float] = None
    source_display: Optional[str] = None
    has_trade_review: Optional[bool] = None
    review_conclusion: Optional[str] = None


class TradeSearchOptionsResponse(BaseModel):
    items: List[TradeSearchOptionItemResponse] = []


class TradeReviewUpsert(BaseModel):
    opportunity_structure: Optional[OpportunityStructure] = None
    edge_source: Optional[EdgeSource] = None
    failure_type: Optional[FailureType] = None
    review_conclusion: Optional[ReviewConclusion] = None

    entry_thesis: Optional[str] = None
    invalidation_valid_evidence: Optional[str] = None
    invalidation_trigger_evidence: Optional[str] = None
    invalidation_boundary: Optional[str] = None
    management_actions: Optional[str] = None
    exit_reason: Optional[str] = None
    tags: Optional[Union[List[str], str]] = None
    review_tags: Optional[str] = None
    research_notes: Optional[str] = None


class TradeReviewResponse(TradeReviewUpsert):
    id: int
    trade_id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    tags: List[str] = []
    review_tags: Optional[str] = None

    class Config:
        from_attributes = True


class TradeReviewTaxonomyResponse(BaseModel):
    opportunity_structure: List[str]
    edge_source: List[str]
    failure_type: List[str]
    review_conclusion: List[str]


class TradeSourceMetadataUpsert(BaseModel):
    broker_name: Optional[str] = None
    source_label: Optional[str] = None
    import_channel: Optional[str] = None
    source_note_snapshot: Optional[str] = None
    parser_version: Optional[str] = None
    derived_from_notes: Optional[bool] = None


class TradeSourceMetadataResponse(TradeSourceMetadataUpsert):
    id: Optional[int] = None
    trade_id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    exists_in_db: bool = False

    class Config:
        from_attributes = True


class TradeBrokerCreate(BaseModel):
    name: str
    account: Optional[str] = None
    password: Optional[str] = None
    extra_info: Optional[str] = None
    notes: Optional[str] = None


class TradeBrokerUpdate(BaseModel):
    name: Optional[str] = None
    account: Optional[str] = None
    password: Optional[str] = None
    extra_info: Optional[str] = None
    notes: Optional[str] = None


class TradeBrokerResponse(TradeBrokerCreate):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ReviewCreate(BaseModel):
    review_type: str
    review_date: date
    title: Optional[str] = None
    review_scope: Optional[str] = "periodic"
    focus_topic: Optional[str] = None
    market_regime: Optional[str] = None
    tags: Optional[Union[List[str], str]] = None
    best_trade: Optional[str] = None
    worst_trade: Optional[str] = None
    discipline_violated: Optional[bool] = None
    loss_acceptable: Optional[bool] = None
    execution_score: Optional[int] = None
    tomorrow_avoid: Optional[str] = None
    profit_source: Optional[str] = None
    loss_source: Optional[str] = None
    continue_trades: Optional[str] = None
    reduce_trades: Optional[str] = None
    repeated_errors: Optional[str] = None
    next_focus: Optional[str] = None
    profit_from_skill: Optional[str] = None
    best_strategy: Optional[str] = None
    profit_eating_behavior: Optional[str] = None
    adjust_symbols: Optional[str] = None
    adjust_position: Optional[str] = None
    pause_patterns: Optional[str] = None
    action_items: Optional[str] = None
    content: Optional[str] = None
    research_notes: Optional[str] = None
    summary: Optional[str] = None
    is_favorite: Optional[bool] = False
    star_rating: Optional[int] = Field(default=None, ge=1, le=5)


class ReviewUpdate(BaseModel):
    review_type: Optional[str] = None
    review_date: Optional[date] = None
    title: Optional[str] = None
    review_scope: Optional[str] = None
    focus_topic: Optional[str] = None
    market_regime: Optional[str] = None
    tags: Optional[Union[List[str], str]] = None
    best_trade: Optional[str] = None
    worst_trade: Optional[str] = None
    discipline_violated: Optional[bool] = None
    loss_acceptable: Optional[bool] = None
    execution_score: Optional[int] = None
    tomorrow_avoid: Optional[str] = None
    profit_source: Optional[str] = None
    loss_source: Optional[str] = None
    continue_trades: Optional[str] = None
    reduce_trades: Optional[str] = None
    repeated_errors: Optional[str] = None
    next_focus: Optional[str] = None
    profit_from_skill: Optional[str] = None
    best_strategy: Optional[str] = None
    profit_eating_behavior: Optional[str] = None
    adjust_symbols: Optional[str] = None
    adjust_position: Optional[str] = None
    pause_patterns: Optional[str] = None
    action_items: Optional[str] = None
    content: Optional[str] = None
    research_notes: Optional[str] = None
    summary: Optional[str] = None
    is_favorite: Optional[bool] = None
    star_rating: Optional[int] = Field(default=None, ge=1, le=5)


class ReviewTradeLinkUpsert(BaseModel):
    trade_id: int
    role: Optional[str] = "linked_trade"
    notes: Optional[str] = None


class TradeSummaryResponse(BaseModel):
    trade_id: int
    trade_date: Optional[date] = None
    instrument_type: Optional[str] = None
    symbol: Optional[str] = None
    contract: Optional[str] = None
    direction: Optional[str] = None
    quantity: Optional[float] = None
    open_price: Optional[float] = None
    close_price: Optional[float] = None
    status: Optional[str] = None
    pnl: Optional[float] = None
    source_display: Optional[str] = None
    has_trade_review: Optional[bool] = None
    review_conclusion: Optional[str] = None


class ReviewTradeLinkResponse(ReviewTradeLinkUpsert):
    id: int
    review_id: int
    trade_summary: Optional[TradeSummaryResponse] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ReviewResponse(ReviewCreate):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    tags: List[str] = []
    tags_text: Optional[str] = None
    trade_links: List[ReviewTradeLinkResponse] = []
    linked_trade_ids: List[int] = []

    class Config:
        from_attributes = True


class ReviewTradeLinksPayload(BaseModel):
    trade_links: List[ReviewTradeLinkUpsert] = []


class ReviewSessionTradeLinkUpsert(BaseModel):
    trade_id: int
    role: Optional[str] = "linked_trade"
    note: Optional[str] = None
    sort_order: Optional[int] = 0


class ReviewSessionCreate(BaseModel):
    title: str
    review_kind: str
    review_scope: Optional[str] = "custom"
    selection_mode: Optional[str] = "manual"
    selection_basis: str
    review_goal: str
    market_regime: Optional[str] = None
    summary: Optional[str] = None
    repeated_errors: Optional[str] = None
    next_focus: Optional[str] = None
    action_items: Optional[str] = None
    content: Optional[str] = None
    research_notes: Optional[str] = None
    tags: Optional[Union[List[str], str]] = None
    filter_snapshot_json: Optional[str] = None
    is_favorite: Optional[bool] = False
    star_rating: Optional[int] = Field(default=None, ge=1, le=5)
    trade_links: List[ReviewSessionTradeLinkUpsert] = []


class ReviewSessionUpdate(BaseModel):
    title: Optional[str] = None
    review_kind: Optional[str] = None
    review_scope: Optional[str] = None
    selection_mode: Optional[str] = None
    selection_basis: Optional[str] = None
    review_goal: Optional[str] = None
    market_regime: Optional[str] = None
    summary: Optional[str] = None
    repeated_errors: Optional[str] = None
    next_focus: Optional[str] = None
    action_items: Optional[str] = None
    content: Optional[str] = None
    research_notes: Optional[str] = None
    tags: Optional[Union[List[str], str]] = None
    filter_snapshot_json: Optional[str] = None
    is_favorite: Optional[bool] = None
    star_rating: Optional[int] = Field(default=None, ge=1, le=5)


class ReviewSessionTradeLinkResponse(ReviewSessionTradeLinkUpsert):
    id: int
    review_session_id: int
    trade_summary: Optional[TradeSummaryResponse] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ReviewSessionResponse(ReviewSessionCreate):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    tags: List[str] = []
    tags_text: Optional[str] = None
    trade_links: List[ReviewSessionTradeLinkResponse] = []
    linked_trade_ids: List[int] = []

    class Config:
        from_attributes = True


class ReviewSessionTradeLinksPayload(BaseModel):
    trade_links: List[ReviewSessionTradeLinkUpsert] = []


class ReviewSessionCreateFromSelection(BaseModel):
    title: str
    review_kind: str
    review_scope: Optional[str] = "custom"
    selection_mode: str = "manual"
    selection_target: Optional[str] = "full_filtered"
    selection_basis: str
    review_goal: str
    market_regime: Optional[str] = None
    summary: Optional[str] = None
    repeated_errors: Optional[str] = None
    next_focus: Optional[str] = None
    action_items: Optional[str] = None
    tags: Optional[Union[List[str], str]] = None
    filter_snapshot_json: Optional[str] = None
    trade_ids: List[int] = []
    filter_params: Optional[dict] = None


class TradePlanTradeLinkUpsert(BaseModel):
    trade_id: int
    note: Optional[str] = None
    sort_order: Optional[int] = 0


class TradePlanReviewSessionLinkUpsert(BaseModel):
    review_session_id: int
    note: Optional[str] = None


class TradePlanCreate(BaseModel):
    title: str
    plan_date: date
    status: Optional[str] = "draft"
    symbol: Optional[str] = None
    contract: Optional[str] = None
    direction_bias: Optional[str] = None
    setup_type: Optional[str] = None
    market_regime: Optional[str] = None
    entry_zone: Optional[str] = None
    stop_loss_plan: Optional[str] = None
    target_plan: Optional[str] = None
    invalid_condition: Optional[str] = None
    thesis: Optional[str] = None
    risk_notes: Optional[str] = None
    execution_checklist: Optional[str] = None
    priority: Optional[str] = "medium"
    tags: Optional[Union[List[str], str]] = None
    source_ref: Optional[str] = None
    post_result_summary: Optional[str] = None
    research_notes: Optional[str] = None
    trade_links: List[TradePlanTradeLinkUpsert] = []


class TradePlanUpdate(BaseModel):
    title: Optional[str] = None
    plan_date: Optional[date] = None
    status: Optional[str] = None
    symbol: Optional[str] = None
    contract: Optional[str] = None
    direction_bias: Optional[str] = None
    setup_type: Optional[str] = None
    market_regime: Optional[str] = None
    entry_zone: Optional[str] = None
    stop_loss_plan: Optional[str] = None
    target_plan: Optional[str] = None
    invalid_condition: Optional[str] = None
    thesis: Optional[str] = None
    risk_notes: Optional[str] = None
    execution_checklist: Optional[str] = None
    priority: Optional[str] = None
    tags: Optional[Union[List[str], str]] = None
    source_ref: Optional[str] = None
    post_result_summary: Optional[str] = None
    research_notes: Optional[str] = None


class TradePlanTradeLinkResponse(TradePlanTradeLinkUpsert):
    id: int
    trade_plan_id: int
    trade_summary: Optional[TradeSummaryResponse] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TradePlanReviewSessionLinkResponse(TradePlanReviewSessionLinkUpsert):
    id: int
    trade_plan_id: int
    created_at: Optional[datetime] = None
    review_session: Optional[ReviewSessionResponse] = None

    class Config:
        from_attributes = True


class TradePlanResponse(TradePlanCreate):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    tags: List[str] = []
    tags_text: Optional[str] = None
    trade_links: List[TradePlanTradeLinkResponse] = []
    linked_trade_ids: List[int] = []
    review_session_links: List[TradePlanReviewSessionLinkResponse] = []

    class Config:
        from_attributes = True


class TradePlanTradeLinksPayload(BaseModel):
    trade_links: List[TradePlanTradeLinkUpsert] = []


class TradePlanReviewSessionLinksPayload(BaseModel):
    review_session_links: List[TradePlanReviewSessionLinkUpsert] = []


class KnowledgeItemCreate(BaseModel):
    category: str
    title: str
    summary: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[Union[List[str], str]] = None
    related_symbol: Optional[str] = None
    related_pattern: Optional[str] = None
    related_regime: Optional[str] = None
    status: Optional[str] = "active"
    priority: Optional[str] = "medium"
    next_action: Optional[str] = None
    due_date: Optional[date] = None
    source_ref: Optional[str] = None
    related_note_ids: Optional[List[int]] = None


class KnowledgeItemUpdate(BaseModel):
    category: Optional[str] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[Union[List[str], str]] = None
    related_symbol: Optional[str] = None
    related_pattern: Optional[str] = None
    related_regime: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    next_action: Optional[str] = None
    due_date: Optional[date] = None
    source_ref: Optional[str] = None
    related_note_ids: Optional[List[int]] = None


class KnowledgeRelatedNoteResponse(BaseModel):
    id: int
    title: str
    note_type: str
    updated_at: Optional[str] = None
    notebook_id: int


class KnowledgeItemResponse(KnowledgeItemCreate):
    id: int
    tags: List[str] = []
    tags_text: Optional[str] = None
    related_notes: List[KnowledgeRelatedNoteResponse] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# 鈹€鈹€ Notebook 鈹€鈹€


class NotebookCreate(BaseModel):
    name: str
    description: Optional[str] = None
    icon: Optional[str] = "馃搧"
    parent_id: Optional[int] = None
    sort_order: Optional[int] = 0


class NotebookUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    parent_id: Optional[int] = None
    sort_order: Optional[int] = None


class NotebookResponse(NotebookCreate):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# 鈹€鈹€ Note 鈹€鈹€


class NoteCreate(BaseModel):
    notebook_id: int
    title: str
    content: Optional[str] = ""
    note_type: Optional[str] = "doc"
    note_date: Optional[date] = None
    tags: Optional[str] = None
    is_pinned: Optional[bool] = False
    word_count: Optional[int] = 0


class NoteUpdate(BaseModel):
    notebook_id: Optional[int] = None
    title: Optional[str] = None
    content: Optional[str] = None
    note_type: Optional[str] = None
    note_date: Optional[date] = None
    tags: Optional[str] = None
    is_pinned: Optional[bool] = None
    word_count: Optional[int] = None


class NoteResponse(NoteCreate):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# 鈹€鈹€ Todo 鈹€鈹€


class TodoCreate(BaseModel):
    content: str
    priority: Optional[str] = "medium"
    source_note_id: Optional[int] = None
    source_anchor_text: Optional[str] = None
    due_at: Optional[datetime] = None
    reminder_at: Optional[datetime] = None


class TodoUpdate(BaseModel):
    content: Optional[str] = None
    is_completed: Optional[bool] = None
    priority: Optional[str] = None
    source_anchor_text: Optional[str] = None
    due_at: Optional[datetime] = None
    reminder_at: Optional[datetime] = None


class TodoResponse(BaseModel):
    id: int
    content: str
    is_completed: bool
    priority: str
    source_note_id: Optional[int] = None
    source_anchor_text: Optional[str] = None
    due_at: Optional[datetime] = None
    reminder_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# 鈹€鈹€ News 鈹€鈹€

