"""FastAPI main application setup with lifespan, CORS, and standard error handling."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from traderadar.api.routers import health
from traderadar.core.config import get_settings
from traderadar.core.db import close_db, ping_db
from traderadar.core.logging import get_logger, setup_logging
from traderadar.core.redis import close_redis, ping_redis, set_heartbeat
from traderadar.core.time import to_iso_utc, utc_now


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Lifespan context manager for startup and shutdown procedures."""
    settings = get_settings()
    setup_logging(log_level=settings.env.LOG_LEVEL, json_format=True)
    logger = get_logger("traderadar.api")
    logger.info("api_starting", version=settings.env.APP_VERSION)

    # Initial check
    await ping_db()
    await ping_redis()
    await set_heartbeat("api", {"status": "healthy", "ts": to_iso_utc(utc_now())})

    yield

    logger.info("api_stopping")
    await close_db()
    await close_redis()


def create_app() -> FastAPI:
    """Create configured FastAPI application instance."""
    settings = get_settings()
    app = FastAPI(
        title="TradeRadar API",
        version=settings.env.APP_VERSION,
        lifespan=lifespan,
        docs_url="/api/docs" if settings.env.APP_VERSION == "dev" else None,
        redoc_url=None,
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.env.APP_VERSION == "dev" else [settings.env.PUBLIC_URL],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Global Exception Handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger = get_logger("traderadar.api.error")
        logger.error("unhandled_exception", path=request.url.path, error=str(exc))
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "Terjadi kesalahan internal pada server.",
                    "detail": str(exc) if settings.env.APP_VERSION == "dev" else None,
                }
            },
        )

    # Include health routers under both /api and root
    app.include_router(health.router, prefix="/api")
    app.include_router(health.router)

    return app


app = create_app()
