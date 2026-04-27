from fastapi import APIRouter

from services import audit_service

router = APIRouter(prefix="/api/audit", tags=["audit"])

router.post("/track")(audit_service.track)
router.get("/logs")(audit_service.list_logs)
router.delete("/logs/{log_id}")(audit_service.delete_log)
