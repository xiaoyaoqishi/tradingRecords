from datetime import date, datetime
from typing import List, Optional, Union

from pydantic import BaseModel, Field

from trade_review_taxonomy import EdgeSource, FailureType, OpportunityStructure, ReviewConclusion


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
    deleted_at: Optional[datetime] = None
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
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


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
