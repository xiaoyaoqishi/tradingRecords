from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.db import Base


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
    is_favorite = Column(Boolean, default=False)
    star_rating = Column(Integer, nullable=True)
    owner_role = Column(String(20), default="admin", index=True)
    is_deleted = Column(Boolean, default=False, index=True)
    deleted_at = Column(DateTime, nullable=True)
    trade_review = relationship("TradeReview", back_populates="trade", uselist=False, cascade="all, delete-orphan")
    source_metadata = relationship("TradeSourceMetadata", back_populates="trade", uselist=False, cascade="all, delete-orphan")


class TradeReview(Base):
    __tablename__ = "trade_reviews"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    trade_id = Column(Integer, ForeignKey("trades.id"), nullable=False, unique=True, index=True)

    opportunity_structure = Column(String(50))
    edge_source = Column(String(50))
    failure_type = Column(String(50))
    review_conclusion = Column(String(50))

    entry_thesis = Column(Text)
    invalidation_valid_evidence = Column(Text)
    invalidation_trigger_evidence = Column(Text)
    invalidation_boundary = Column(Text)
    management_actions = Column(Text)
    exit_reason = Column(Text)
    review_tags = Column(Text)
    research_notes = Column(Text)

    trade = relationship("Trade", back_populates="trade_review")
    tag_links = relationship("TradeReviewTagLink", back_populates="trade_review", cascade="all, delete-orphan")


class TradeSourceMetadata(Base):
    __tablename__ = "trade_source_metadata"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    trade_id = Column(Integer, ForeignKey("trades.id"), nullable=False, unique=True, index=True)
    broker_name = Column(String(100))
    source_label = Column(String(100))
    import_channel = Column(String(50))
    source_note_snapshot = Column(Text)
    parser_version = Column(String(30))
    derived_from_notes = Column(Boolean, default=True)

    trade = relationship("Trade", back_populates="source_metadata")


class TradeBroker(Base):
    __tablename__ = "trade_brokers"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    name = Column(String(100), nullable=False, unique=True)
    account = Column(String(100), nullable=True)
    password = Column(String(200), nullable=True)
    extra_info = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    owner_role = Column(String(20), default="admin", index=True)
    is_deleted = Column(Boolean, default=False, index=True)
    deleted_at = Column(DateTime, nullable=True)


class TagTerm(Base):
    __tablename__ = "tag_terms"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    name = Column(String(100), nullable=False)
    name_key = Column(String(120), nullable=False, unique=True, index=True)


class TradeReviewTagLink(Base):
    __tablename__ = "trade_review_tag_links"
    __table_args__ = (
        UniqueConstraint("trade_review_id", "tag_term_id", name="uq_trade_review_tag"),
    )

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, server_default=func.now())

    trade_review_id = Column(Integer, ForeignKey("trade_reviews.id"), nullable=False, index=True)
    tag_term_id = Column(Integer, ForeignKey("tag_terms.id"), nullable=False, index=True)

    trade_review = relationship("TradeReview", back_populates="tag_links")
    tag_term = relationship("TagTerm")
