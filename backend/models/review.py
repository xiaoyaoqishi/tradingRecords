from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.db import Base


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
    title = Column(String(200))
    review_scope = Column(String(30), default="periodic")
    focus_topic = Column(String(200))
    market_regime = Column(String(100))
    tags_text = Column("tags", Text)
    action_items = Column(Text)
    content = Column(Text)
    research_notes = Column(Text)
    summary = Column(Text)
    is_favorite = Column(Boolean, default=False)
    star_rating = Column(Integer, nullable=True)
    trade_links = relationship("ReviewTradeLink", back_populates="review", cascade="all, delete-orphan")
    tag_links = relationship("ReviewTagLink", back_populates="review", cascade="all, delete-orphan")


class ReviewTradeLink(Base):
    __tablename__ = "review_trade_links"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    review_id = Column(Integer, ForeignKey("reviews.id"), nullable=False, index=True)
    trade_id = Column(Integer, ForeignKey("trades.id"), nullable=False, index=True)
    role = Column(String(30), default="linked_trade")
    notes = Column(Text)

    review = relationship("Review", back_populates="trade_links")
    trade = relationship("Trade")


class ReviewSession(Base):
    __tablename__ = "review_sessions"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    title = Column(String(200), nullable=False)
    review_kind = Column(String(40), nullable=False, index=True)
    review_scope = Column(String(40), default="custom", index=True)
    selection_mode = Column(String(40), default="manual", index=True)
    selection_basis = Column(Text, nullable=False)
    review_goal = Column(Text, nullable=False)
    market_regime = Column(String(100))
    summary = Column(Text)
    repeated_errors = Column(Text)
    next_focus = Column(Text)
    action_items = Column(Text)
    content = Column(Text)
    research_notes = Column(Text)
    tags_text = Column("tags", Text)
    filter_snapshot_json = Column(Text)
    is_favorite = Column(Boolean, default=False)
    star_rating = Column(Integer, nullable=True)
    owner_role = Column(String(20), default="admin", index=True)
    is_deleted = Column(Boolean, default=False, index=True)
    deleted_at = Column(DateTime, nullable=True)

    trade_links = relationship("ReviewSessionTradeLink", back_populates="review_session", cascade="all, delete-orphan")


class ReviewSessionTradeLink(Base):
    __tablename__ = "review_session_trade_links"
    __table_args__ = (
        UniqueConstraint("review_session_id", "trade_id", name="uq_review_session_trade"),
    )

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    review_session_id = Column(Integer, ForeignKey("review_sessions.id"), nullable=False, index=True)
    trade_id = Column(Integer, ForeignKey("trades.id"), nullable=False, index=True)
    role = Column(String(40), default="linked_trade")
    note = Column(Text)
    sort_order = Column(Integer, default=0)

    review_session = relationship("ReviewSession", back_populates="trade_links")
    trade = relationship("Trade")


class TradePlan(Base):
    __tablename__ = "trade_plans"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    title = Column(String(200), nullable=False)
    plan_date = Column(Date, nullable=False, index=True)
    status = Column(String(20), nullable=False, default="draft", index=True)
    symbol = Column(String(50))
    contract = Column(String(50))
    direction_bias = Column(String(20))
    setup_type = Column(String(80))
    market_regime = Column(String(100))
    entry_zone = Column(Text)
    stop_loss_plan = Column(Text)
    target_plan = Column(Text)
    invalid_condition = Column(Text)
    thesis = Column(Text)
    risk_notes = Column(Text)
    execution_checklist = Column(Text)
    priority = Column(String(20), default="medium")
    tags_text = Column("tags", Text)
    source_ref = Column(String(200))
    post_result_summary = Column(Text)
    research_notes = Column(Text)
    owner_role = Column(String(20), default="admin", index=True)
    is_deleted = Column(Boolean, default=False, index=True)
    deleted_at = Column(DateTime, nullable=True)

    trade_links = relationship("TradePlanTradeLink", back_populates="trade_plan", cascade="all, delete-orphan")
    review_session_links = relationship("TradePlanReviewSessionLink", back_populates="trade_plan", cascade="all, delete-orphan")


class TradePlanTradeLink(Base):
    __tablename__ = "trade_plan_trade_links"
    __table_args__ = (
        UniqueConstraint("trade_plan_id", "trade_id", name="uq_trade_plan_trade"),
    )

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, server_default=func.now())

    trade_plan_id = Column(Integer, ForeignKey("trade_plans.id"), nullable=False, index=True)
    trade_id = Column(Integer, ForeignKey("trades.id"), nullable=False, index=True)
    note = Column(Text)
    sort_order = Column(Integer, default=0)

    trade_plan = relationship("TradePlan", back_populates="trade_links")
    trade = relationship("Trade")


class TradePlanReviewSessionLink(Base):
    __tablename__ = "trade_plan_review_session_links"
    __table_args__ = (
        UniqueConstraint("trade_plan_id", "review_session_id", name="uq_trade_plan_review_session"),
    )

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, server_default=func.now())

    trade_plan_id = Column(Integer, ForeignKey("trade_plans.id"), nullable=False, index=True)
    review_session_id = Column(Integer, ForeignKey("review_sessions.id"), nullable=False, index=True)
    note = Column(Text)

    trade_plan = relationship("TradePlan", back_populates="review_session_links")
    review_session = relationship("ReviewSession")


class ReviewTagLink(Base):
    __tablename__ = "review_tag_links"
    __table_args__ = (
        UniqueConstraint("review_id", "tag_term_id", name="uq_review_tag"),
    )

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, server_default=func.now())

    review_id = Column(Integer, ForeignKey("reviews.id"), nullable=False, index=True)
    tag_term_id = Column(Integer, ForeignKey("tag_terms.id"), nullable=False, index=True)

    review = relationship("Review", back_populates="tag_links")
    tag_term = relationship("TagTerm")
