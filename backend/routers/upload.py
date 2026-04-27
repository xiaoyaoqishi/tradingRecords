from fastapi import APIRouter

from services import upload_service

router = APIRouter(prefix="/api", tags=["upload"])

router.post("/upload")(upload_service.upload)
router.get("/uploads/{filename}")(upload_service.get_upload)
