from fastapi import APIRouter, Depends

from core.deps import require_admin
from services import monitor_service

router = APIRouter(prefix="/api/monitor", tags=["monitor"], dependencies=[Depends(require_admin)])

router.get("/realtime")(monitor_service.realtime)
router.get("/history")(monitor_service.history)
router.get("/sites")(monitor_service.list_sites)
router.post("/sites")(monitor_service.create_site)
router.put("/sites/{site_id}")(monitor_service.update_site)
router.delete("/sites/{site_id}")(monitor_service.delete_site)
router.get("/sites/{site_id}/results")(monitor_service.site_results)
