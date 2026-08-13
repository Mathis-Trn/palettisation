"""Application FastAPI — couche d'adaptation HTTP versionnée (`/api/v1`) au-dessus du service
applicatif headless. Ne contient aucune logique métier."""

from __future__ import annotations

import logging
import os
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from palletizer import __version__
from palletizer.api.routes import router
from palletizer.api.schemas import ErrorDetail, ErrorResponse
from palletizer.domain.errors import PalletizerError

logger = logging.getLogger("palletizer.api")


def _allowed_origins() -> list[str]:
    """CORS piloté par `ALLOWED_ORIGINS` (liste séparée par des virgules) ; jamais `*` si
    `APP_ENV=production`."""
    app_env = os.environ.get("APP_ENV", "development")
    raw = os.environ.get("ALLOWED_ORIGINS", "")
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    if not origins:
        return [] if app_env == "production" else ["http://localhost:3000"]
    if "*" in origins and app_env == "production":
        raise RuntimeError("ALLOWED_ORIGINS=* est interdit lorsque APP_ENV=production.")
    return origins


def _is_production() -> bool:
    return os.environ.get("APP_ENV", "development") == "production"


def create_app() -> FastAPI:
    app = FastAPI(
        title="Palletizer API",
        version=__version__,
        description="API headless de palettisation 3D et de chargement transport.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def correlation_id_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[JSONResponse]]
    ) -> JSONResponse:
        correlation_id = request.headers.get("X-Request-Id", str(uuid.uuid4()))
        request.state.correlation_id = correlation_id
        response = await call_next(request)
        response.headers["X-Request-Id"] = correlation_id
        return response

    @app.exception_handler(HTTPException)
    async def handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
        correlation_id = getattr(request.state, "correlation_id", "unknown")
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error=ErrorDetail(
                    code=f"HTTP_{exc.status_code}",
                    message=str(exc.detail),
                    correlation_id=correlation_id,
                )
            ).model_dump(),
            headers={"X-Request-Id": correlation_id},
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        correlation_id = getattr(request.state, "correlation_id", "unknown")
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="VALIDATION_ERROR",
                    message=str(exc.errors()),
                    correlation_id=correlation_id,
                )
            ).model_dump(),
            headers={"X-Request-Id": correlation_id},
        )

    @app.exception_handler(PalletizerError)
    async def handle_palletizer_error(request: Request, exc: PalletizerError) -> JSONResponse:
        correlation_id = getattr(request.state, "correlation_id", "unknown")
        logger.warning("palletizer_error correlation_id=%s error=%s", correlation_id, exc)
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(
                error=ErrorDetail(
                    code=type(exc).__name__, message=str(exc), correlation_id=correlation_id
                )
            ).model_dump(),
            headers={"X-Request-Id": correlation_id},
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        correlation_id = getattr(request.state, "correlation_id", "unknown")
        logger.exception("unexpected_error correlation_id=%s", correlation_id)
        message = "Erreur interne du serveur." if _is_production() else str(exc)
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="INTERNAL_ERROR", message=message, correlation_id=correlation_id
                )
            ).model_dump(),
            headers={"X-Request-Id": correlation_id},
        )

    app.include_router(router)
    return app


app = create_app()
