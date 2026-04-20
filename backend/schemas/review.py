from datetime import date, datetime
from typing import List, Optional, Union

from pydantic import BaseModel, Field

from trade_review_taxonomy import EdgeSource, FailureType, OpportunityStructure, ReviewConclusion
from schemas.trading import TradeSummaryResponse


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
    deleted_at: Optional[datetime] = None
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
    deleted_at: Optional[datetime] = None
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
