"""TrustModel Agent Eval - FastAPI Application."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.auth import router as auth_router
from app.api.v1.router import api_router
from app.config import settings
from app.core.database import engine
from app.core.logging import setup_logging

# Setup structured logging
setup_logging()
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    # Startup
    logger.info(
        "Starting TrustModel Agent Eval",
        version=settings.app_version,
        debug=settings.debug,
    )

    # Initialize database connection pool
    async with engine.begin() as conn:
        logger.info("Database connection established")

    yield

    # Shutdown
    logger.info("Shutting down TrustModel Agent Eval")
    await engine.dispose()


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Enterprise trust infrastructure for AI agents - SSL/TLS for the Agent Economy",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else "/openapi.json",
    lifespan=lifespan,
)

# ═══════════════════════════════════════════════════════════════════════════════
# Middleware
# ═══════════════════════════════════════════════════════════════════════════════

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════════════════════════════
# Health Check
# ═══════════════════════════════════════════════════════════════════════════════


@app.get("/health", tags=["Health"])
async def health_check() -> JSONResponse:
    """Health check endpoint for container orchestration."""
    return JSONResponse(
        content={
            "status": "healthy",
            "version": settings.app_version,
            "service": "trustmodel-api",
        }
    )


@app.get("/", tags=["Health"])
async def root() -> JSONResponse:
    """Root endpoint with API information."""
    return JSONResponse(
        content={
            "name": settings.app_name,
            "version": settings.app_version,
            "description": "Enterprise trust infrastructure for AI agents",
            "docs": "/docs" if settings.debug else "Contact support for API access",
            "endpoints": {
                "auth": "/auth",
                "api": "/v1",
                "health": "/health",
            },
        }
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Routers
# ═══════════════════════════════════════════════════════════════════════════════

app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(api_router, prefix="/v1")


# ═══════════════════════════════════════════════════════════════════════════════
# Exception Handlers
# ═══════════════════════════════════════════════════════════════════════════════


@app.exception_handler(Exception)
async def global_exception_handler(request, exc: Exception) -> JSONResponse:
    """Global exception handler for unhandled errors."""
    logger.error(
        "Unhandled exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": "An unexpected error occurred",
        },
    )
