from fastapi import APIRouter

from services import upload_service

router = APIRouter(prefix="/api", tags=["upload"])
router.add_api_route("/upload", upload_service.upload, methods=["POST"])
router.add_api_route("/uploads/{filename}", upload_service.get_upload, methods=["GET"])
