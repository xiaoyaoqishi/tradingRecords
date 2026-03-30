from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime


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


class TradeResponse(TradeCreate):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ReviewCreate(BaseModel):
    review_type: str
    review_date: date
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
    content: Optional[str] = None
    summary: Optional[str] = None


class ReviewUpdate(BaseModel):
    review_type: Optional[str] = None
    review_date: Optional[date] = None
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
    content: Optional[str] = None
    summary: Optional[str] = None


class ReviewResponse(ReviewCreate):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
