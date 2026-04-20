from fastapi import APIRouter

from services import audit_service

router = APIRouter(prefix="/api", tags=["audit"])
router.add_api_route("/audit/track", audit_service.track, methods=["POST"])
router.add_api_route("/audit/logs", audit_service.list_logs, methods=["GET"])
router.add_api_route("/audit/logs/{log_id}", audit_service.delete_log, methods=["DELETE"])
