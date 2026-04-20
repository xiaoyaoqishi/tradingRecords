from fastapi import APIRouter
from sqlalchemy import text

from core.config import settings
from core.db import SessionLocal

router = APIRouter(prefix="/api", tags=["health"])


def health():
    db_ok = False
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    finally:
        db.close()
    return {"ok": True, "app": settings.app_title, "version": settings.app_version, "db": {"ok": db_ok}}


router.add_api_route("/health", health, methods=["GET"])
