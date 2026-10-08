import logging
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from nudge.config import get_settings
from nudge.errors import NudgeError
from nudge.logging import request_id_var, setup_logging
from nudge.web.routes import health, me

log = logging.getLogger(__name__)


def _error_body(request: Request, code: str, message: str) -> dict:
    return {
        "error": {
            "code": code,
            "message": message,
            "request_id": getattr(request.state, "request_id", None),
        }
    }


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.http = httpx.AsyncClient(timeout=10)
    log.info("api started")
    yield
    await app.state.http.aclose()
    log.info("api stopped")


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level, json_output=settings.env != "local")

    app = FastAPI(title="Nudge API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        request.state.request_id = rid
        token = request_id_var.set(rid)
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers["x-request-id"] = rid
        return response

    @app.exception_handler(NudgeError)
    async def handle_nudge_error(request: Request, exc: NudgeError) -> JSONResponse:
        if exc.status_code >= 500:
            log.error("request failed: %s", exc.message, exc_info=exc)
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(request, exc.code, exc.message),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error")
        return JSONResponse(
            status_code=500,
            content=_error_body(request, "internal_error", "Something went wrong"),
        )

    app.include_router(health.router)
    app.include_router(me.router)
    return app
