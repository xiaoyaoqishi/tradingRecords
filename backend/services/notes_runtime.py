from __future__ import annotations

from datetime import datetime
import json
import re
from typing import List, Optional

from bs4 import BeautifulSoup
from fastapi import Depends, HTTPException, Query
from sqlalchemy.orm import Session

from core import context
from core.db import SessionLocal, get_db
from core.security import normalize_owner_role
from models import Note, NoteLink, Notebook, TodoItem
from schemas.notes import NoteCreate, NoteUpdate, NotebookCreate, NotebookUpdate, TodoCreate, TodoUpdate


TODO_PRIORITIES = {"low", "medium", "high"}


def _current_is_admin() -> bool:
    return context.is_admin()


def _owner_role_value_for_create() -> str:
    return "admin" if _current_is_admin() else "user"


def _owner_role_filter_for_admin(model, owner_role: Optional[str]):
    if not _current_is_admin():
        return None
    role = normalize_owner_role(owner_role)
    if role:
        return model.owner_role == role
    return None


def init_default_notebooks():
    db = SessionLocal()
    try:
        if db.query(Notebook).count() == 0:
            db.add_all(
                [
                    Notebook(name="日记本", icon="📔", sort_order=0, owner_role="admin"),
                    Notebook(name="文档", icon="📄", sort_order=1, owner_role="admin"),
                ]
            )
            db.commit()
    finally:
        db.close()


def _normalize_todo_priority(priority: Optional[str]) -> str:
    val = (priority or "medium").strip().lower()
    if val not in TODO_PRIORITIES:
        raise HTTPException(400, "priority 必须是 low / medium / high")
    return val


def list_notebooks(owner_role: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(Notebook)
    role_filter = _owner_role_filter_for_admin(Notebook, owner_role)
    if role_filter is not None:
        q = q.filter(role_filter)
    return q.order_by(Notebook.sort_order, Notebook.id).all()


def create_notebook(data: NotebookCreate, db: Session = Depends(get_db)):
    obj = Notebook(**data.model_dump(), owner_role=_owner_role_value_for_create())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_notebook(nb_id: int, data: NotebookUpdate, db: Session = Depends(get_db)):
    nb = db.query(Notebook).filter(Notebook.id == nb_id).first()
    if not nb:
        raise HTTPException(404, "Notebook not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(nb, k, v)
    db.commit()
    db.refresh(nb)
    return nb


def delete_notebook(nb_id: int, db: Session = Depends(get_db)):
    nb = db.query(Notebook).filter(Notebook.id == nb_id).first()
    if not nb:
        raise HTTPException(404, "Notebook not found")
    db.delete(nb)
    db.commit()
    return {"ok": True}


def list_notes(
    notebook_id: Optional[int] = None,
    note_type: Optional[str] = None,
    note_date: Optional[str] = None,
    keyword: Optional[str] = None,
    tag: Optional[str] = None,
    is_pinned: Optional[bool] = None,
    owner_role: Optional[str] = None,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    q = db.query(Note).filter(Note.is_deleted == False)  # noqa: E712
    role_filter = _owner_role_filter_for_admin(Note, owner_role)
    if role_filter is not None:
        q = q.filter(role_filter)
    if notebook_id:
        q = q.filter(Note.notebook_id == notebook_id)
    if note_type:
        q = q.filter(Note.note_type == note_type)
    if note_date:
        q = q.filter(Note.note_date == note_date)
    if keyword:
        q = q.filter((Note.title.contains(keyword)) | (Note.content.contains(keyword)))
    if tag:
        q = q.filter(Note.tags.contains(tag))
    if is_pinned is not None:
        q = q.filter(Note.is_pinned == is_pinned)
    return q.order_by(Note.is_pinned.desc(), Note.updated_at.desc()).offset((page - 1) * size).limit(size).all()


def note_stats(db: Session = Depends(get_db)):
    from sqlalchemy import func as sqlfunc

    diary_count = db.query(Note).filter(Note.note_type == "diary", Note.is_deleted == False).count()  # noqa: E712
    doc_count = db.query(Note).filter(Note.note_type == "doc", Note.is_deleted == False).count()  # noqa: E712
    diary_words = (
        db.query(sqlfunc.coalesce(sqlfunc.sum(Note.word_count), 0))
        .filter(Note.note_type == "diary", Note.is_deleted == False)  # noqa: E712
        .scalar()
    )
    doc_words = (
        db.query(sqlfunc.coalesce(sqlfunc.sum(Note.word_count), 0))
        .filter(Note.note_type == "doc", Note.is_deleted == False)  # noqa: E712
        .scalar()
    )
    recent_docs = (
        db.query(Note)
        .filter(Note.note_type == "doc", Note.is_deleted == False)  # noqa: E712
        .order_by(Note.updated_at.desc())
        .limit(8)
        .all()
    )
    return {
        "diary_count": diary_count,
        "doc_count": doc_count,
        "diary_word_count": diary_words,
        "doc_word_count": doc_words,
        "recent_docs": [{"id": n.id, "title": n.title or "无标题", "updated_at": str(n.updated_at)} for n in recent_docs],
    }


def history_today(db: Session = Depends(get_db)):
    from datetime import date as dt_date
    from sqlalchemy import func as sqlfunc

    today = dt_date.today()
    md = today.strftime("%m-%d")
    notes = (
        db.query(Note)
        .filter(
            Note.note_type == "diary",
            Note.note_date.isnot(None),
            Note.is_deleted == False,  # noqa: E712
            sqlfunc.strftime("%m-%d", Note.note_date) == md,
            sqlfunc.strftime("%Y", Note.note_date) != str(today.year),
        )
        .order_by(Note.note_date.desc())
        .all()
    )
    return [{"id": n.id, "title": n.title, "note_date": str(n.note_date)} for n in notes]


def diary_tree(db: Session = Depends(get_db)):
    notes = (
        db.query(Note.id, Note.title, Note.note_date)
        .filter(Note.note_type == "diary", Note.note_date.isnot(None), Note.is_deleted == False)  # noqa: E712
        .order_by(Note.note_date.desc())
        .all()
    )
    tree = {}
    for n in notes:
        y = str(n.note_date.year) + "年"
        m = str(n.note_date.month) + "月"
        d = str(n.note_date.day).zfill(2) + "日"
        tree.setdefault(y, {}).setdefault(m, []).append({"id": n.id, "title": n.title, "date": str(n.note_date), "day": d})
    return tree


def _extract_tiptap_text(node) -> str:
    if isinstance(node, dict):
        parts = []
        txt = node.get("text")
        if isinstance(txt, str) and txt.strip():
            parts.append(txt.strip())
        content = node.get("content")
        if isinstance(content, list):
            for child in content:
                child_txt = _extract_tiptap_text(child)
                if child_txt:
                    parts.append(child_txt)
        return " ".join(parts).strip()
    if isinstance(node, list):
        return " ".join(filter(None, (_extract_tiptap_text(x) for x in node))).strip()
    return ""


def _note_summary_text(content: Optional[str], title: Optional[str]) -> str:
    fallback = (title or "").strip() or "（无内容）"
    if not content:
        return fallback
    raw = str(content).strip()
    if not raw:
        return fallback
    try:
        obj = json.loads(raw)
        text_out = _extract_tiptap_text(obj)
    except Exception:
        text_out = BeautifulSoup(raw, "html.parser").get_text(" ", strip=True)
    text_out = re.sub(r"\s+", " ", text_out).strip()
    if not text_out:
        return fallback
    return text_out[:120]


def _note_plain_text(content: Optional[str], title: Optional[str]) -> str:
    fallback = (title or "").strip()
    if not content:
        return fallback
    raw = str(content).strip()
    if not raw:
        return fallback
    try:
        obj = json.loads(raw)
        text_out = _extract_tiptap_text(obj)
    except Exception:
        text_out = BeautifulSoup(raw, "html.parser").get_text(" ", strip=True)
    text_out = re.sub(r"\s+", " ", text_out).strip()
    return text_out or fallback


def _make_search_snippet(text: str, keyword: str, width: int = 90) -> str:
    if not text:
        return ""
    key = (keyword or "").strip().lower()
    if not key:
        return text[:width]
    low = text.lower()
    idx = low.find(key)
    if idx < 0:
        return text[:width]
    start = max(0, idx - width // 2)
    end = min(len(text), idx + len(keyword) + width // 2)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""
    return f"{prefix}{text[start:end]}{suffix}"


def _split_keywords(q: str) -> List[str]:
    return [k for k in re.split(r"\s+", (q or "").strip().lower()) if k]


def _search_rank(title: str, plain: str, keys: List[str]) -> int:
    if not keys:
        return 0
    t = (title or "").lower()
    p = (plain or "").lower()
    score = 0
    for k in keys:
        if k in t:
            score += 8
        if k in p:
            score += 3
        if t.startswith(k):
            score += 2
    if all(k in t for k in keys):
        score += 6
    if all(k in p for k in keys):
        score += 2
    return score


def _parse_note_wikilinks(text: str) -> List[tuple[str, Optional[str]]]:
    out = []
    seen = set()
    for m in re.finditer(r"\[\[([^\[\]\n]{1,220})\]\]", text or ""):
        raw = (m.group(1) or "").strip()
        if not raw:
            continue
        name, heading = (raw.split("#", 1) + [None])[:2]
        name = (name or "").strip()
        heading = (heading or "").strip() or None
        if not name:
            continue
        key = (name.lower(), (heading or "").lower())
        if key in seen:
            continue
        seen.add(key)
        out.append((name, heading))
    return out


def _resolve_link_target_id(db: Session, target_name: str) -> Optional[int]:
    name = (target_name or "").strip()
    if not name:
        return None
    note = (
        db.query(Note)
        .filter(Note.title == name, Note.note_type == "doc", Note.is_deleted == False)  # noqa: E712
        .order_by(Note.updated_at.desc())
        .first()
    )
    if note:
        return note.id
    note = db.query(Note).filter(Note.title == name, Note.is_deleted == False).order_by(Note.updated_at.desc()).first()  # noqa: E712
    return note.id if note else None


def _index_note_links(db: Session, note: Note):
    db.query(NoteLink).filter(NoteLink.source_note_id == note.id).delete(synchronize_session=False)
    plain = _note_plain_text(note.content, note.title)
    for name, heading in _parse_note_wikilinks(plain):
        db.add(
            NoteLink(
                source_note_id=note.id,
                target_note_id=_resolve_link_target_id(db, name),
                target_name=name,
                target_heading=heading,
            )
        )


def _refresh_link_targets(db: Session):
    links = db.query(NoteLink).all()
    for lk in links:
        lk.target_note_id = _resolve_link_target_id(db, lk.target_name)


def index_links_for_existing_notes():
    db = SessionLocal()
    try:
        notes = db.query(Note).filter(Note.is_deleted == False).all()  # noqa: E712
        db.query(NoteLink).delete(synchronize_session=False)
        for n in notes:
            _index_note_links(db, n)
        db.commit()
    finally:
        db.close()


def search_notes(q: str = Query(..., min_length=1), note_type: Optional[str] = Query(None), limit: int = Query(30, ge=1, le=100), db: Session = Depends(get_db)):
    kw = q.strip()
    keys = _split_keywords(kw)
    if not keys:
        return []
    rows = db.query(Note).filter(Note.is_deleted == False).order_by(Note.updated_at.desc()).limit(500).all()  # noqa: E712
    out = []
    for n in rows:
        if note_type and n.note_type != note_type:
            continue
        title = (n.title or "").strip()
        plain = _note_plain_text(n.content, title)
        t_low = title.lower()
        p_low = plain.lower()
        if not all((k in t_low) or (k in p_low) for k in keys):
            continue
        rank = _search_rank(title, plain, keys)
        out.append(
            {
                "id": n.id,
                "title": title or "无标题",
                "note_type": n.note_type,
                "note_date": str(n.note_date) if n.note_date else None,
                "updated_at": str(n.updated_at) if n.updated_at else None,
                "snippet": _make_search_snippet(plain, keys[0]),
                "notebook_id": n.notebook_id,
                "_rank": rank,
                "_ts": n.updated_at.timestamp() if n.updated_at else 0,
            }
        )
    out.sort(key=lambda x: (-x["_rank"], -x["_ts"], -x["id"]))
    trimmed = out[:limit]
    for item in trimmed:
        item.pop("_rank", None)
        item.pop("_ts", None)
    return trimmed


def resolve_note_link(name: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    target_name = name.strip()
    target_id = _resolve_link_target_id(db, target_name)
    if not target_id:
        return {"resolved": False, "matches": []}
    n = db.query(Note).filter(Note.id == target_id, Note.is_deleted == False).first()  # noqa: E712
    if not n:
        return {"resolved": False, "matches": []}
    return {
        "resolved": True,
        "matches": [
            {
                "id": n.id,
                "title": n.title,
                "note_type": n.note_type,
                "notebook_id": n.notebook_id,
                "updated_at": str(n.updated_at) if n.updated_at else None,
            }
        ],
    }


def note_backlinks(note_id: int, limit: int = Query(100, ge=1, le=300), db: Session = Depends(get_db)):
    target = db.query(Note).filter(Note.id == note_id, Note.is_deleted == False).first()  # noqa: E712
    if not target:
        raise HTTPException(404, "Note not found")
    rows = (
        db.query(NoteLink, Note)
        .join(Note, Note.id == NoteLink.source_note_id)
        .filter(NoteLink.target_note_id == note_id, Note.is_deleted == False)  # noqa: E712
        .order_by(Note.updated_at.desc())
        .limit(limit)
        .all()
    )
    out = []
    for lk, src in rows:
        plain = _note_plain_text(src.content, src.title)
        needle = f"[[{lk.target_name}]]"
        if lk.target_heading:
            needle = f"[[{lk.target_name}#{lk.target_heading}]]"
        out.append(
            {
                "source_note_id": src.id,
                "source_title": src.title or "无标题",
                "source_note_type": src.note_type,
                "source_updated_at": str(src.updated_at) if src.updated_at else None,
                "snippet": _make_search_snippet(plain, needle),
                "target_name": lk.target_name,
                "target_heading": lk.target_heading,
            }
        )
    return out


def diary_summaries(year: int = Query(..., ge=1970, le=2100), month: Optional[int] = Query(None, ge=1, le=12), db: Session = Depends(get_db)):
    from sqlalchemy import extract

    q = db.query(Note).filter(Note.note_type == "diary", Note.note_date.isnot(None), Note.is_deleted == False)  # noqa: E712
    q = q.filter(extract("year", Note.note_date) == year)
    if month is not None:
        q = q.filter(extract("month", Note.note_date) == month)
    notes = q.order_by(Note.note_date.asc()).all()
    return [{"id": n.id, "note_date": str(n.note_date), "summary": _note_summary_text(n.content, n.title)} for n in notes]


def notes_calendar(year: int = Query(...), month: int = Query(...), db: Session = Depends(get_db)):
    from sqlalchemy import extract

    dates = (
        db.query(Note.note_date)
        .filter(
            Note.note_type == "diary",
            Note.note_date.isnot(None),
            Note.is_deleted == False,  # noqa: E712
            extract("year", Note.note_date) == year,
            extract("month", Note.note_date) == month,
        )
        .distinct()
        .all()
    )
    return [str(d[0]) for d in dates]


def create_note(data: NoteCreate, db: Session = Depends(get_db)):
    nb = db.query(Notebook).filter(Notebook.id == data.notebook_id).first()
    if not nb:
        raise HTTPException(404, "Notebook not found")
    obj = Note(**data.model_dump(), owner_role=nb.owner_role or _owner_role_value_for_create())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    _index_note_links(db, obj)
    _refresh_link_targets(db)
    db.commit()
    return obj


def get_note(note_id: int, db: Session = Depends(get_db)):
    n = db.query(Note).filter(Note.id == note_id, Note.is_deleted == False).first()  # noqa: E712
    if not n:
        raise HTTPException(404, "Note not found")
    return n


def update_note(note_id: int, data: NoteUpdate, db: Session = Depends(get_db)):
    n = db.query(Note).filter(Note.id == note_id, Note.is_deleted == False).first()  # noqa: E712
    if not n:
        raise HTTPException(404, "Note not found")
    old_title = (n.title or "").strip()
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(n, k, v)
    _index_note_links(db, n)
    if (n.title or "").strip() != old_title:
        _refresh_link_targets(db)
    db.commit()
    db.refresh(n)
    return n


def delete_note(note_id: int, db: Session = Depends(get_db)):
    n = db.query(Note).filter(Note.id == note_id, Note.is_deleted == False).first()  # noqa: E712
    if not n:
        raise HTTPException(404, "Note not found")
    n.is_deleted = True
    n.deleted_at = datetime.now()
    db.query(NoteLink).filter(NoteLink.source_note_id == note_id).delete(synchronize_session=False)
    db.query(NoteLink).filter(NoteLink.target_note_id == note_id).update({NoteLink.target_note_id: None}, synchronize_session=False)
    db.commit()
    return {"ok": True}


def list_recycle_notes(note_type: Optional[str] = Query(None), db: Session = Depends(get_db)):
    q = db.query(Note).filter(Note.is_deleted == True)  # noqa: E712
    if note_type:
        q = q.filter(Note.note_type == note_type)
    return q.order_by(Note.deleted_at.desc()).all()


def restore_note(note_id: int, db: Session = Depends(get_db)):
    n = db.query(Note).filter(Note.id == note_id, Note.is_deleted == True).first()  # noqa: E712
    if not n:
        raise HTTPException(404, "Note not found in recycle bin")
    n.is_deleted = False
    n.deleted_at = None
    _index_note_links(db, n)
    _refresh_link_targets(db)
    db.commit()
    db.refresh(n)
    return n


def purge_note(note_id: int, db: Session = Depends(get_db)):
    n = db.query(Note).filter(Note.id == note_id).first()
    if not n:
        raise HTTPException(404, "Note not found")
    db.query(NoteLink).filter(NoteLink.source_note_id == note_id).delete(synchronize_session=False)
    db.query(NoteLink).filter(NoteLink.target_note_id == note_id).delete(synchronize_session=False)
    db.delete(n)
    db.commit()
    return {"ok": True}


def clear_recycle_notes(note_type: Optional[str] = Query(None), db: Session = Depends(get_db)):
    q = db.query(Note).filter(Note.is_deleted == True)  # noqa: E712
    if note_type:
        q = q.filter(Note.note_type == note_type)
    rows = q.all()
    if not rows:
        return {"ok": True, "deleted": 0}
    ids = [n.id for n in rows]
    db.query(NoteLink).filter(NoteLink.source_note_id.in_(ids)).delete(synchronize_session=False)
    db.query(NoteLink).filter(NoteLink.target_note_id.in_(ids)).delete(synchronize_session=False)
    db.query(Note).filter(Note.id.in_(ids)).delete(synchronize_session=False)
    db.commit()
    return {"ok": True, "deleted": len(ids)}


def list_todos(
    include_completed: bool = Query(True),
    keyword: Optional[str] = Query(None),
    owner_role: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(TodoItem)
    role_filter = _owner_role_filter_for_admin(TodoItem, owner_role)
    if role_filter is not None:
        q = q.filter(role_filter)
    if not include_completed:
        q = q.filter(TodoItem.is_completed == False)  # noqa: E712
    if keyword and keyword.strip():
        q = q.filter(TodoItem.content.contains(keyword.strip()))
    items = q.order_by(TodoItem.is_completed.asc(), TodoItem.created_at.desc()).all()
    priority_rank = {"high": 0, "medium": 1, "low": 2}
    items.sort(
        key=lambda x: (
            1 if x.is_completed else 0,
            0 if x.due_at else 1,
            x.due_at.timestamp() if x.due_at else 0,
            priority_rank.get(x.priority, 1),
            -(x.created_at.timestamp() if x.created_at else 0),
        )
    )
    return items


def create_todo(data: TodoCreate, db: Session = Depends(get_db)):
    content = (data.content or "").strip()
    if not content:
        raise HTTPException(400, "待办内容不能为空")
    priority = _normalize_todo_priority(data.priority)
    src = None
    if data.source_note_id is not None:
        src = db.query(Note).filter(Note.id == data.source_note_id).first()
        if not src:
            raise HTTPException(404, "source_note_id 对应日记不存在")
    if data.due_at and data.reminder_at and data.reminder_at > data.due_at:
        raise HTTPException(400, "提醒时间不能晚于截止时间")
    obj = TodoItem(
        content=content,
        priority=priority,
        is_completed=False,
        source_note_id=data.source_note_id,
        source_anchor_text=(data.source_anchor_text or "").strip() or None,
        due_at=data.due_at,
        reminder_at=data.reminder_at,
        owner_role=(src.owner_role if src else _owner_role_value_for_create()),
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_todo(todo_id: int, data: TodoUpdate, db: Session = Depends(get_db)):
    obj = db.query(TodoItem).filter(TodoItem.id == todo_id).first()
    if not obj:
        raise HTTPException(404, "Todo not found")
    updates = data.model_dump(exclude_unset=True)
    if "content" in updates:
        updates["content"] = (updates["content"] or "").strip()
        if not updates["content"]:
            raise HTTPException(400, "待办内容不能为空")
    if "priority" in updates:
        updates["priority"] = _normalize_todo_priority(updates["priority"])
    if "source_anchor_text" in updates:
        updates["source_anchor_text"] = (updates["source_anchor_text"] or "").strip() or None
    due_at = updates.get("due_at", obj.due_at)
    reminder_at = updates.get("reminder_at", obj.reminder_at)
    if due_at and reminder_at and reminder_at > due_at:
        raise HTTPException(400, "提醒时间不能晚于截止时间")
    for k, v in updates.items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


def delete_todo(todo_id: int, db: Session = Depends(get_db)):
    obj = db.query(TodoItem).filter(TodoItem.id == todo_id).first()
    if not obj:
        raise HTTPException(404, "Todo not found")
    db.delete(obj)
    db.commit()
    return {"ok": True}
