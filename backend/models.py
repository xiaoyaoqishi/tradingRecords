from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, Date, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # --- 成交流水层 ---
    trade_date = Column(Date, nullable=False)
    instrument_type = Column(String(20), nullable=False)
    symbol = Column(String(50), nullable=False)
    contract = Column(String(50))
    category = Column(String(50))
    direction = Column(String(10), nullable=False)
    open_time = Column(DateTime, nullable=False)
    close_time = Column(DateTime)
    open_price = Column(Float, nullable=False)
    close_price = Column(Float)
    quantity = Column(Float, nullable=False)
    margin = Column(Float)
    commission = Column(Float, default=0)
    slippage = Column(Float, default=0)
    pnl = Column(Float)
    pnl_points = Column(Float)
    holding_duration = Column(String(50))
    is_overnight = Column(Boolean, default=False)
    trading_session = Column(String(20))
    status = Column(String(10), default="open")

    # 期货特有
    is_main_contract = Column(String(20))
    is_near_delivery = Column(Boolean, default=False)
    is_contract_switch = Column(Boolean, default=False)
    is_high_volatility = Column(Boolean, default=False)
    is_near_data_release = Column(Boolean, default=False)

    # --- 交易决策层 ---
    entry_logic = Column(Text)
    exit_logic = Column(Text)
    strategy_type = Column(String(50))
    market_condition = Column(String(50))
    timeframe = Column(String(20))
    core_signal = Column(Text)
    stop_loss_plan = Column(Float)
    target_plan = Column(Float)
    followed_plan = Column(Boolean)

    # --- 行为纪律层 ---
    is_planned = Column(Boolean)
    is_impulsive = Column(Boolean, default=False)
    is_chasing = Column(Boolean, default=False)
    is_holding_loss = Column(Boolean, default=False)
    is_early_profit = Column(Boolean, default=False)
    is_extended_stop = Column(Boolean, default=False)
    is_overweight = Column(Boolean, default=False)
    is_revenge = Column(Boolean, default=False)
    is_emotional = Column(Boolean, default=False)
    mental_state = Column(String(20))
    physical_state = Column(String(20))

    # --- 交易前中后 ---
    pre_opportunity = Column(Text)
    pre_win_reason = Column(Text)
    pre_risk = Column(Text)
    during_match_expectation = Column(Text)
    during_plan_changed = Column(Text)
    post_quality = Column(String(50))
    post_repeat = Column(Boolean)
    post_root_cause = Column(Text)
    post_replicable = Column(Boolean)

    # --- 标签与复盘 ---
    error_tags = Column(Text)
    review_note = Column(Text)
    notes = Column(Text)


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    review_type = Column(String(10), nullable=False)
    review_date = Column(Date, nullable=False)

    # 日复盘
    best_trade = Column(Text)
    worst_trade = Column(Text)
    discipline_violated = Column(Boolean)
    loss_acceptable = Column(Boolean)
    execution_score = Column(Integer)
    tomorrow_avoid = Column(Text)

    # 周复盘
    profit_source = Column(Text)
    loss_source = Column(Text)
    continue_trades = Column(Text)
    reduce_trades = Column(Text)
    repeated_errors = Column(Text)
    next_focus = Column(Text)

    # 月复盘
    profit_from_skill = Column(Text)
    best_strategy = Column(Text)
    profit_eating_behavior = Column(Text)
    adjust_symbols = Column(Text)
    adjust_position = Column(Text)
    pause_patterns = Column(Text)

    # 通用
    content = Column(Text)
    summary = Column(Text)


class Notebook(Base):
    __tablename__ = "notebooks"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    name = Column(String(100), nullable=False)
    description = Column(Text)
    icon = Column(String(10), default="📁")
    parent_id = Column(Integer, ForeignKey("notebooks.id"), nullable=True)
    sort_order = Column(Integer, default=0)

    notes = relationship("Note", back_populates="notebook", cascade="all, delete-orphan")


class Note(Base):
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    notebook_id = Column(Integer, ForeignKey("notebooks.id"), nullable=False)
    title = Column(String(200), nullable=False)
    content = Column(Text, default="")
    note_type = Column(String(10), default="doc")
    note_date = Column(Date, nullable=True)
    tags = Column(Text)
    is_pinned = Column(Boolean, default=False)
    word_count = Column(Integer, default=0)
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime, nullable=True)

    notebook = relationship("Notebook", back_populates="notes")


class TodoItem(Base):
    __tablename__ = "todo_items"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    content = Column(Text, nullable=False)
    is_completed = Column(Boolean, default=False)
    priority = Column(String(10), default="medium")
    source_note_id = Column(Integer, ForeignKey("notes.id"), nullable=True)


class NewsIssue(Base):
    __tablename__ = "news_issues"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    title = Column(String(255), nullable=False)
    issue_date = Column(Date, nullable=True)
    source_repo = Column(String(255), nullable=False)
    source_path = Column(String(500), nullable=False, unique=True)
    source_sha = Column(String(80), nullable=True)
    source_url = Column(String(500), nullable=True)
    local_epub_path = Column(String(500), nullable=True)

    content_en = Column(Text, default="")
    content_zh = Column(Text, default="")
    status = Column(String(30), default="downloaded")
    translated_at = Column(DateTime, nullable=True)
