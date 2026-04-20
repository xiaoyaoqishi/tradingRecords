from fastapi import APIRouter

from services import auth_service

router = APIRouter(prefix="/api", tags=["auth"])
router.add_api_route("/auth/check", auth_service.auth_check, methods=["GET"])
router.add_api_route("/auth/setup", auth_service.auth_setup, methods=["POST"])
router.add_api_route("/auth/login", auth_service.auth_login, methods=["POST"])
router.add_api_route("/auth/logout", auth_service.auth_logout, methods=["POST"])
