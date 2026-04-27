from fastapi import APIRouter

from services import poem_service

router = APIRouter(prefix="/api/poem", tags=["poem"])

router.get("/daily")(poem_service.get_daily_poem)
