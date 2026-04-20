from datetime import date, datetime
from typing import List, Optional, Union

from pydantic import BaseModel, Field

from trade_review_taxonomy import EdgeSource, FailureType, OpportunityStructure, ReviewConclusion


class KnowledgeItemCreate(BaseModel):
    category: str
    title: str
    summary: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[Union[List[str], str]] = None
    related_symbol: Optional[str] = None
    related_pattern: Optional[str] = None
    related_regime: Optional[str] = None
    status: Optional[str] = "active"
    priority: Optional[str] = "medium"
    next_action: Optional[str] = None
    due_date: Optional[date] = None
    source_ref: Optional[str] = None
    related_note_ids: Optional[List[int]] = None


class KnowledgeItemUpdate(BaseModel):
    category: Optional[str] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[Union[List[str], str]] = None
    related_symbol: Optional[str] = None
    related_pattern: Optional[str] = None
    related_regime: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    next_action: Optional[str] = None
    due_date: Optional[date] = None
    source_ref: Optional[str] = None
    related_note_ids: Optional[List[int]] = None


class KnowledgeRelatedNoteResponse(BaseModel):
    id: int
    title: str
    note_type: str
    updated_at: Optional[str] = None
    notebook_id: int


class KnowledgeItemResponse(KnowledgeItemCreate):
    id: int
    tags: List[str] = []
    tags_text: Optional[str] = None
    related_notes: List[KnowledgeRelatedNoteResponse] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# 鈹€鈹€ Notebook 鈹€鈹€
