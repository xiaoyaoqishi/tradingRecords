from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.db import Base


class LedgerCategory(Base):
    __tablename__ = "ledger_categories"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("ledger_categories.id"), nullable=True, index=True)
    name = Column(String(120), nullable=False, index=True)
    category_type = Column(String(20), nullable=False, index=True, default="expense")
    sort_order = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    owner_role = Column(String(20), default="admin", index=True)
    is_deleted = Column(Boolean, default=False, index=True)
    deleted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    parent = relationship("LedgerCategory", remote_side=[id], backref="children", uselist=False)


class LedgerImportBatch(Base):
    __tablename__ = "ledger_import_batches"

    id = Column(Integer, primary_key=True, index=True)
    source_type = Column(String(40), nullable=False, default="unknown", index=True)
    file_name = Column(String(255), nullable=False)
    file_hash = Column(String(64), nullable=False, index=True)
    file_path = Column(String(500), nullable=False)
    status = Column(String(30), nullable=False, default="uploaded", index=True)
    total_rows = Column(Integer, nullable=False, default=0)
    parsed_rows = Column(Integer, nullable=False, default=0)
    matched_rows = Column(Integer, nullable=False, default=0)
    review_rows = Column(Integer, nullable=False, default=0)
    duplicate_rows = Column(Integer, nullable=False, default=0)
    owner_role = Column(String(20), default="admin", index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    rows = relationship("LedgerImportRow", back_populates="batch", cascade="all, delete-orphan")


class LedgerRule(Base):
    __tablename__ = "ledger_rules"

    id = Column(Integer, primary_key=True, index=True)
    rule_type = Column(String(40), nullable=False, index=True)
    priority = Column(Integer, nullable=False, default=100, index=True)
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    match_mode = Column(String(20), nullable=False, default="contains")
    pattern = Column(String(255), nullable=False)
    source_channel_condition = Column(String(50), nullable=True, index=True)
    platform_condition = Column(String(50), nullable=True, index=True)
    direction_condition = Column(String(20), nullable=True, index=True)
    amount_min = Column(Float, nullable=True)
    amount_max = Column(Float, nullable=True)
    target_platform = Column(String(50), nullable=True)
    target_merchant = Column(String(200), nullable=True)
    target_txn_kind = Column(String(40), nullable=True)
    target_scene = Column(String(80), nullable=True)
    target_category_id = Column(Integer, ForeignKey("ledger_categories.id"), nullable=True, index=True)
    target_subcategory_id = Column(Integer, ForeignKey("ledger_categories.id"), nullable=True, index=True)
    explain_text = Column(String(255), nullable=True)
    confidence_score = Column(Float, nullable=False, default=0.7)
    owner_role = Column(String(20), default="admin", index=True)
    is_deleted = Column(Boolean, default=False, index=True)
    deleted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class LedgerMerchant(Base):
    __tablename__ = "ledger_merchants"

    id = Column(Integer, primary_key=True, index=True)
    canonical_name = Column(String(200), nullable=False, index=True)
    aliases_json = Column(Text, nullable=False, default="[]")
    default_category_id = Column(Integer, ForeignKey("ledger_categories.id"), nullable=True, index=True)
    default_subcategory_id = Column(Integer, ForeignKey("ledger_categories.id"), nullable=True, index=True)
    tags_json = Column(Text, nullable=False, default="[]")
    hit_count = Column(Integer, nullable=False, default=0)
    owner_role = Column(String(20), default="admin", index=True)
    is_deleted = Column(Boolean, default=False, index=True)
    deleted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class LedgerImportRow(Base):
    __tablename__ = "ledger_import_rows"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("ledger_import_batches.id"), nullable=False, index=True)
    row_index = Column(Integer, nullable=False)
    account_id = Column(Integer, nullable=True, index=True)
    raw_payload_json = Column(Text, nullable=False, default="{}")
    raw_text = Column(Text, nullable=True)
    normalized_text = Column(Text, nullable=True)
    text_fingerprint = Column(String(64), nullable=True, index=True)
    occurred_at = Column(DateTime, nullable=True, index=True)
    occurred_bucket = Column(String(25), nullable=True, index=True)
    amount = Column(Float, nullable=True)
    direction = Column(String(20), nullable=True, index=True)
    balance = Column(Float, nullable=True)
    source_channel = Column(String(50), nullable=True, index=True)
    txn_kind = Column(String(40), nullable=True, index=True)
    scene_candidate = Column(String(80), nullable=True, index=True)
    platform = Column(String(50), nullable=True, index=True)
    merchant_raw = Column(String(200), nullable=True, index=True)
    merchant_normalized = Column(String(200), nullable=True, index=True)
    merchant_id = Column(Integer, ForeignKey("ledger_merchants.id"), nullable=True, index=True)
    category_id = Column(Integer, ForeignKey("ledger_categories.id"), nullable=True, index=True)
    subcategory_id = Column(Integer, ForeignKey("ledger_categories.id"), nullable=True, index=True)
    confidence = Column(Float, nullable=False, default=0.0)

    source_rule_id = Column(Integer, ForeignKey("ledger_rules.id"), nullable=True, index=True)
    source_confidence = Column(Float, nullable=True)
    source_explain = Column(String(255), nullable=True)

    merchant_rule_id = Column(Integer, ForeignKey("ledger_rules.id"), nullable=True, index=True)
    merchant_confidence = Column(Float, nullable=True)
    merchant_explain = Column(String(255), nullable=True)

    category_rule_id = Column(Integer, ForeignKey("ledger_rules.id"), nullable=True, index=True)
    category_confidence = Column(Float, nullable=True)
    category_explain = Column(String(255), nullable=True)

    duplicate_key = Column(String(120), nullable=True, index=True)
    duplicate_type = Column(String(30), nullable=True, index=True)
    duplicate_score = Column(Float, nullable=True)
    duplicate_basis_json = Column(Text, nullable=True)

    review_status = Column(String(30), nullable=False, default="pending", index=True)
    review_note = Column(Text, nullable=True)
    low_confidence_reason = Column(String(255), nullable=True)
    suggested_candidates_json = Column(Text, nullable=True)
    execution_trace_json = Column(Text, nullable=True)

    owner_role = Column(String(20), default="admin", index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    batch = relationship("LedgerImportBatch", back_populates="rows")


class LedgerTransaction(Base):
    __tablename__ = "ledger_transactions"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("ledger_import_batches.id"), nullable=True, index=True)
    import_row_id = Column(Integer, ForeignKey("ledger_import_rows.id"), nullable=True, index=True)
    account_id = Column(Integer, nullable=True, index=True)
    occurred_at = Column(DateTime, nullable=False, index=True)
    amount = Column(Float, nullable=False)
    direction = Column(String(20), nullable=False, index=True)
    currency = Column(String(10), nullable=False, default="CNY")
    balance = Column(Float, nullable=True)
    source_channel = Column(String(50), nullable=True, index=True)
    txn_kind = Column(String(40), nullable=True, index=True)
    scene_candidate = Column(String(80), nullable=True, index=True)
    platform = Column(String(50), nullable=True, index=True)
    merchant_raw = Column(String(200), nullable=True, index=True)
    merchant_normalized = Column(String(200), nullable=True, index=True)
    merchant_id = Column(Integer, ForeignKey("ledger_merchants.id"), nullable=True, index=True)
    description = Column(Text, nullable=True)
    normalized_text = Column(Text, nullable=True)
    text_fingerprint = Column(String(64), nullable=True, index=True)
    category_id = Column(Integer, ForeignKey("ledger_categories.id"), nullable=True, index=True)
    subcategory_id = Column(Integer, ForeignKey("ledger_categories.id"), nullable=True, index=True)
    duplicate_key = Column(String(120), nullable=True, index=True)
    confidence_score = Column(Float, nullable=True)
    review_note = Column(Text, nullable=True)
    owner_role = Column(String(20), default="admin", index=True)
    is_deleted = Column(Boolean, default=False, index=True)
    deleted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
