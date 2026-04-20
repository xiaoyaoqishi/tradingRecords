from fastapi import APIRouter

from services import monitor_service

router = APIRouter(prefix="/api", tags=["monitor"])
router.add_api_route("/monitor/realtime", monitor_service.realtime, methods=["GET"])
router.add_api_route("/monitor/history", monitor_service.history, methods=["GET"])
router.add_api_route("/monitor/sites", monitor_service.list_sites, methods=["GET"])
router.add_api_route("/monitor/sites", monitor_service.create_site, methods=["POST"])
router.add_api_route("/monitor/sites/{site_id}", monitor_service.update_site, methods=["PUT"])
router.add_api_route("/monitor/sites/{site_id}", monitor_service.delete_site, methods=["DELETE"])
router.add_api_route("/monitor/sites/{site_id}/results", monitor_service.site_results, methods=["GET"])
