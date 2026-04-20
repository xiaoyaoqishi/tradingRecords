from datetime import date, datetime
from typing import List, Optional, Union

from pydantic import BaseModel, Field

from trade_review_taxonomy import EdgeSource, FailureType, OpportunityStructure, ReviewConclusion


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
