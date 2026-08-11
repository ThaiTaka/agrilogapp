"""FastAPI application factory.

Run locally:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

`--host 0.0.0.0` matters: the Android emulator reaches the host machine at
10.0.2.2, not 127.0.0.1, so binding to loopback only makes the API invisible
to the app.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app import __version__
from app.api.deps import DbSession
from app.core.config import settings
from app.core.timeutils import now_ms
from app.db.session import engine

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger("agrilog")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("AgriLog API v%s starting (env=%s)", __version__, settings.APP_ENV)
    if settings.is_production and settings.JWT_SECRET.startswith("insecure-"):
        raise RuntimeError(
            "JWT_SECRET is still the development default while APP_ENV=production. "
            "Generate one: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
        )
    yield
    engine.dispose()
    logger.info("AgriLog API shut down")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=__version__,
        description=(
            "Offline-first farming diary, supply inventory and cost tracking for "
            "smallholder households. Mobile clients write to a local SQLite database "
            "and reconcile through the /sync endpoints when connectivity allows."
        ),
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        # The sync client reads the server clock from this header to detect
        # its own drift without parsing a response body.
        expose_headers=["X-Server-Time"],
    )

    @app.middleware("http")
    async def add_server_time_header(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Server-Time"] = str(now_ms())
        return response

    _register_health_routes(app)
    _register_exception_handlers(app)
    _register_v1_routers(app)
    return app


def _register_health_routes(app: FastAPI) -> None:
    @app.get("/health", tags=["meta"], summary="Liveness probe")
    def health() -> dict:
        return {"status": "ok", "version": __version__, "server_time_ms": now_ms()}

    @app.get("/health/db", tags=["meta"], summary="Readiness probe (database reachable)")
    def health_db(db: DbSession) -> JSONResponse:
        # Goes through the same `get_db` dependency every route uses, rather
        # than opening its own connection off the module-level engine. A probe
        # that exercises a different path than real traffic can report healthy
        # while every actual request fails.
        try:
            db.execute(text("SELECT 1"))
            return JSONResponse({"status": "ok", "database": "reachable"})
        except Exception as exc:  # noqa: BLE001 - probe must never raise
            logger.error("Database health check failed: %s", exc)
            return JSONResponse(
                {"status": "error", "database": "unreachable", "detail": str(exc)},
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )


def _register_exception_handlers(app: FastAPI) -> None:
    from sqlalchemy.exc import IntegrityError

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
        """Turn a constraint violation into a 409, not a 500.

        Most IntegrityErrors here are meaningful application outcomes -- a
        duplicate supply name, a second auto-expense for the same stock
        movement -- and the client can act on a 409. The raw SQL is logged but
        never returned, since it names internal columns.
        """
        logger.warning("IntegrityError on %s %s: %s", request.method, request.url.path, exc.orig)
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "detail": "The request conflicts with existing data.",
                "constraint": _extract_constraint_name(str(exc.orig)),
            },
        )


def _extract_constraint_name(message: str) -> str | None:
    marker = 'constraint "'
    if marker in message:
        return message.split(marker, 1)[1].split('"', 1)[0]
    return None


def _register_v1_routers(app: FastAPI) -> None:
    """Mount the v1 API.

    Routers are added here as each module lands (auth, seasons, diary,
    supplies, finance, reports, sync).
    """
    from app.api.v1 import auth, diary, seasons, supplies

    app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
    app.include_router(seasons.router, prefix=settings.API_V1_PREFIX)
    app.include_router(supplies.router, prefix=settings.API_V1_PREFIX)
    app.include_router(diary.season_router, prefix=settings.API_V1_PREFIX)
    app.include_router(diary.router, prefix=settings.API_V1_PREFIX)


app = create_app()
