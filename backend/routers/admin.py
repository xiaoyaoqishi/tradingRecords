from fastapi import APIRouter

from services import admin_service

router = APIRouter(prefix="/api/admin", tags=["admin"])

router.get("/users")(admin_service.list_users)
router.post("/users")(admin_service.create_user)
router.post("/users/{user_id}/toggle-active")(admin_service.toggle_user_active)
router.post("/users/{user_id}/reset-password")(admin_service.reset_user_password)
router.put("/users/{user_id}")(admin_service.update_user)
router.delete("/users/{user_id}")(admin_service.delete_user)
