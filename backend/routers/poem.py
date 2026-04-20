from fastapi import APIRouter

from services import poem_service

router = APIRouter(prefix="/api", tags=["poem"])
router.add_api_route("/poem/daily", poem_service.get_daily_poem, methods=["GET"])
