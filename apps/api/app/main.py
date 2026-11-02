"""Fábrica de la aplicación FastAPI: middlewares de seguridad, manejo de errores y routers."""

import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.errors import DomainError
from app.core.logging import configure_logging
from app.routers import admin, auth, catalog, generations, health, tracks, wallet

logger = logging.getLogger("sonaria.http")

_MUTATING = {"POST", "PUT", "PATCH", "DELETE"}


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="Sonaria API",
        version="0.1.0",
        description="API de generación musical, créditos y biblioteca. Todas las rutas bajo /v1.",
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "Idempotency-Key", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
        max_age=600,
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        started = time.perf_counter()

        # Protección CSRF básica: las sesiones van en cookie, así que las mutaciones con cuerpo
        # deben enviar JSON. Un formulario HTML cross-site no puede hacerlo sin preflight CORS.
        if request.method in _MUTATING and request.headers.get("content-length", "0") not in ("", "0"):
            ctype = request.headers.get("content-type", "")
            if not ctype.startswith("application/json") and not request.url.path.endswith("/webhooks/wompi"):
                return JSONResponse(
                    status_code=415,
                    content={"detail": {"code": "unsupported_media_type", "message": "Se requiere application/json."}},
                )

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Frame-Options"] = "DENY"
        if settings.app_env == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        logger.info(
            "request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 1),
            },
        )
        return response

    @app.exception_handler(DomainError)
    async def domain_error_handler(_: Request, exc: DomainError) -> JSONResponse:
        http = exc.to_http()
        return JSONResponse(status_code=http.status_code, content={"detail": http.detail})

    prefix = "/v1"
    for module in (health, auth, catalog, wallet, generations, tracks, admin):
        app.include_router(module.router, prefix=prefix)
    return app


app = create_app()
