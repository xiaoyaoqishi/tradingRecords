from fastapi import APIRouter

from services import auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])

router.get("/check")(auth_service.auth_check)
router.post("/setup")(auth_service.auth_setup)
router.post("/login")(auth_service.auth_login)
router.post("/logout")(auth_service.auth_logout)
