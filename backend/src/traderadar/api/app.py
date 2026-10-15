"""FastAPI main application setup with lifespan, CORS, and auth gatekeeper."""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from traderadar.api.routers import analysis, auth, health, market, ws
from traderadar.core.config import get_settings
from traderadar.core.db import close_db, ping_db
from traderadar.core.logging import get_logger, setup_logging
from traderadar.core.redis import close_redis, ping_redis, set_heartbeat
from traderadar.core.security import decode_access_token
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
        openapi_url="/api/openapi.json" if settings.env.APP_VERSION == "dev" else None,
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

    # Auth Gatekeeper Middleware: all /api/* routes except public whitelist require authentication
    @app.middleware("http")
    async def auth_gatekeeper_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        path = request.url.path

        # Allow OPTIONS for CORS preflight
        if request.method == "OPTIONS":
            return await call_next(request)

        # Only protect /api/ paths
        if path.startswith("/api/"):
            public_exact = {
                "/api/health",
                "/api/health/full",
                "/api/auth/login",
                "/api/auth/refresh",
                "/api/docs",
                "/api/openapi.json",
            }
            if path not in public_exact and not path.startswith("/api/docs/"):
                token: str | None = None
                access_cookie = request.cookies.get("access_token")
                if access_cookie:
                    token = access_cookie
                else:
                    auth_header = request.headers.get("authorization")
                    if auth_header and auth_header.lower().startswith("bearer "):
                        token = auth_header[7:].strip()

                if not token:
                    return JSONResponse(
                        status_code=401,
                        content={
                            "error": {
                                "code": "UNAUTHORIZED",
                                "message": "Autentikasi diperlukan. Silakan login terlebih dahulu.",
                                "detail": None,
                            }
                        },
                    )

                try:
                    decode_access_token(token)
                except Exception as exc:
                    return JSONResponse(
                        status_code=401,
                        content={
                            "error": {
                                "code": "UNAUTHORIZED",
                                "message": "Sesi tidak valid atau telah kedaluwarsa.",
                                "detail": str(exc) if settings.env.APP_VERSION == "dev" else None,
                            }
                        },
                    )

        return await call_next(request)

    # Uniform HTTP Exception Handler
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict):
            return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": "HTTP_ERROR",
                    "message": str(exc.detail),
                    "detail": None,
                }
            },
        )

    # Uniform Validation Exception Handler
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Data permintaan tidak valid.",
                    "detail": exc.errors(),
                }
            },
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

    # Register Routers
    app.include_router(health.router, prefix="/api")
    app.include_router(health.router)
    app.include_router(auth.router, prefix="/api")
    app.include_router(market.router, prefix="/api")
    app.include_router(analysis.router, prefix="/api")
    app.include_router(ws.router)

    return app


app = create_app()
