import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from auth import verify_token
from core import context
from core.config import settings
from core.db import SessionLocal
from models import User


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request.state.request_id = str(uuid.uuid4())

        username = "xiaoyao"
        role = "admin"
        is_admin = True

        if not settings.dev_mode and request.url.path.startswith("/api/"):
            token = request.cookies.get(settings.auth_cookie)
            parsed_username = verify_token(token) if token else None
            public_paths = set(settings.auth_whitelist) | {"/api/health"}
            if request.url.path not in public_paths and not parsed_username:
                return JSONResponse(status_code=401, content={"detail": "未登录"})
            if parsed_username:
                db = SessionLocal()
                try:
                    user = db.query(User).filter(User.username == parsed_username, User.is_active == True).first()  # noqa: E712
                finally:
                    db.close()
                if not user and request.url.path not in public_paths:
                    return JSONResponse(status_code=401, content={"detail": "账号不可用"})
                if user:
                    username = user.username
                    role = (user.role or "user").strip().lower()
                    is_admin = role == "admin"

        request.state.username = username
        request.state.role = role
        request.state.is_admin = is_admin

        token_u = context.current_username.set(username)
        token_r = context.current_role.set(role)
        token_a = context.current_is_admin.set(is_admin)
        try:
            response = await call_next(request)
            response.headers["X-Request-Id"] = request.state.request_id
            return response
        finally:
            context.current_username.reset(token_u)
            context.current_role.reset(token_r)
            context.current_is_admin.reset(token_a)


def register_middleware(app: FastAPI) -> None:
    app.add_middleware(RequestContextMiddleware)
