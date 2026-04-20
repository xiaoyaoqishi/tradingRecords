from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.db import Base


class KnowledgeItem(Base):
    __tablename__ = "knowledge_items"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    category = Column(String(50), nullable=False, index=True)
    title = Column(String(200), nullable=False, index=True)
    summary = Column(Text)
    content = Column(Text)
    tags_text = Column("tags", Text)

    related_symbol = Column(String(50))
    related_pattern = Column(String(100))
    related_regime = Column(String(100))

    status = Column(String(30), default="active")
    priority = Column(String(20), default="medium")
    next_action = Column(Text)
    due_date = Column(Date)
    source_ref = Column(String(200))
    owner_role = Column(String(20), default="admin", index=True)
    is_deleted = Column(Boolean, default=False, index=True)
    deleted_at = Column(DateTime, nullable=True)
    tag_links = relationship("KnowledgeItemTagLink", back_populates="knowledge_item", cascade="all, delete-orphan")
    note_links = relationship("KnowledgeItemNoteLink", back_populates="knowledge_item", cascade="all, delete-orphan")


class KnowledgeItemTagLink(Base):
    __tablename__ = "knowledge_item_tag_links"
    __table_args__ = (
        UniqueConstraint("knowledge_item_id", "tag_term_id", name="uq_knowledge_item_tag"),
    )

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, server_default=func.now())

    knowledge_item_id = Column(Integer, ForeignKey("knowledge_items.id"), nullable=False, index=True)
    tag_term_id = Column(Integer, ForeignKey("tag_terms.id"), nullable=False, index=True)

    knowledge_item = relationship("KnowledgeItem", back_populates="tag_links")
    tag_term = relationship("TagTerm")


class KnowledgeItemNoteLink(Base):
    __tablename__ = "knowledge_item_note_links"
    __table_args__ = (
        UniqueConstraint("knowledge_item_id", "note_id", name="uq_knowledge_item_note"),
    )

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, server_default=func.now())

    knowledge_item_id = Column(Integer, ForeignKey("knowledge_items.id"), nullable=False, index=True)
    note_id = Column(Integer, ForeignKey("notes.id"), nullable=False, index=True)
    sort_order = Column(Integer, default=0)

    knowledge_item = relationship("KnowledgeItem", back_populates="note_links")
    note = relationship("Note")
