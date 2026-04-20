from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.errors import register_error_handlers
from core.middleware import register_middleware
from routers import api_router
from services.runtime import init_runtime


def create_app() -> FastAPI:
    init_runtime()
    app = FastAPI(title=settings.app_title, version=settings.app_version)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_middleware(app)
    register_error_handlers(app)
    app.include_router(api_router)
    return app
