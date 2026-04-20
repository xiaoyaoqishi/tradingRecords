from fastapi import APIRouter

from services import admin_service

router = APIRouter(prefix="/api", tags=["admin"])
router.add_api_route("/admin/users", admin_service.list_users, methods=["GET"])
router.add_api_route("/admin/users", admin_service.create_user, methods=["POST"])
router.add_api_route("/admin/users/{user_id}/toggle-active", admin_service.toggle_user_active, methods=["POST"])
router.add_api_route("/admin/users/{user_id}/reset-password", admin_service.reset_user_password, methods=["POST"])
router.add_api_route("/admin/users/{user_id}", admin_service.update_user, methods=["PUT"])
router.add_api_route("/admin/users/{user_id}", admin_service.delete_user, methods=["DELETE"])
