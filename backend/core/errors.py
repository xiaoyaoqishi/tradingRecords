from datetime import datetime
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400, detail: Any = None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.detail = detail
        super().__init__(message)


def error_payload(code: str, message: str, request_id: Optional[str] = None, detail: Any = None):
    body = {
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id,
            "timestamp": datetime.utcnow().isoformat(),
        }
    }
    if detail is not None:
        body["error"]["detail"] = detail
    return body


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        return JSONResponse(status_code=exc.status_code, content=error_payload(exc.code, exc.message, getattr(request.state, "request_id", None), exc.detail))

    @app.exception_handler(HTTPException)
    async def handle_http_error(request: Request, exc: HTTPException):
        return JSONResponse(status_code=exc.status_code, content=error_payload("http_error", str(exc.detail), getattr(request.state, "request_id", None)))

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception):
        return JSONResponse(status_code=500, content=error_payload("internal_error", str(exc), getattr(request.state, "request_id", None)))
