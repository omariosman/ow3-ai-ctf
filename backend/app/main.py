"""FastAPI application entrypoint (plan Phase 2).

Security posture (plan sections 16 & 23):
* ORM-only DB access -> parameterized queries.
* CORS restricted to configured origins.
* Request bodies capped in size.
* Basic rate limiting on the inference oracle.
* /docs, /redoc, /openapi.json disabled outside development.
* Safe, non-leaking error responses.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .database import init_db
from .logging_config import configure_logging
from .routes import challenges as challenges_routes
from .routes import context_hijack as context_hijack_routes
from .routes import model_crate as model_crate_routes
from .routes import predict as predict_routes
from .routes import trace_leak as trace_leak_routes
from .routes import poisoned_memory as poisoned_memory_routes
from .routes import release_roulette as release_roulette_routes
from .routes import render_trap as render_trap_routes

configure_logging()
logger = logging.getLogger("ctf")


def create_app() -> FastAPI:
    settings = get_settings()
    docs_enabled = settings.is_development
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        # Disable interactive docs/schema outside development so a production-like
        # challenge deployment does not advertise its endpoints (plan section 16).
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    @app.middleware("http")
    async def limit_body_size(request: Request, call_next):
        """Reject oversized request bodies early (plan section 23)."""
        cl = request.headers.get("content-length")
        if cl is not None:
            try:
                if int(cl) > settings.max_request_bytes:
                    return JSONResponse(
                        status_code=413, content={"detail": "Request body too large"}
                    )
            except ValueError:
                return JSONResponse(
                    status_code=400, content={"detail": "Invalid Content-Length"}
                )
        return await call_next(request)

    @app.exception_handler(Exception)
    async def safe_error_handler(request: Request, exc: Exception):
        """Never leak internals/stack traces to clients (plan section 23)."""
        logger.exception("unhandled error at %s", request.url.path)
        return JSONResponse(
            status_code=500, content={"detail": "Internal server error"}
        )

    app.include_router(challenges_routes.router)
    app.include_router(predict_routes.router)
    app.include_router(release_roulette_routes.router)
    app.include_router(render_trap_routes.router)
    app.include_router(model_crate_routes.router)
    app.include_router(context_hijack_routes.router)
    app.include_router(trace_leak_routes.router)
    app.include_router(poisoned_memory_routes.router)

    @app.get("/api/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok", "app": settings.app_name}

    @app.on_event("startup")
    def _startup() -> None:
        init_db()
        logger.info("Database initialized (env=%s)", settings.environment)

    return app


app = create_app()
