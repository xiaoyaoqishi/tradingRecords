from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.db import Base


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
    owner_role = Column(String(20), default="admin", index=True)

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
    owner_role = Column(String(20), default="admin", index=True)
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime, nullable=True)

    notebook = relationship("Notebook", back_populates="notes")


class NoteLink(Base):
    __tablename__ = "note_links"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    source_note_id = Column(Integer, ForeignKey("notes.id"), nullable=False, index=True)
    target_note_id = Column(Integer, ForeignKey("notes.id"), nullable=True, index=True)
    target_name = Column(String(200), nullable=False)
    target_heading = Column(String(200), nullable=True)


class TodoItem(Base):
    __tablename__ = "todo_items"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    content = Column(Text, nullable=False)
    is_completed = Column(Boolean, default=False)
    priority = Column(String(10), default="medium")
    source_note_id = Column(Integer, ForeignKey("notes.id"), nullable=True)
    source_anchor_text = Column(Text, nullable=True)
    due_at = Column(DateTime, nullable=True)
    reminder_at = Column(DateTime, nullable=True)
    owner_role = Column(String(20), default="admin", index=True)
