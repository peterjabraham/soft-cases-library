"""
FastAPI application entry point.

Configures CORS, registers routers, runs startup checks
(env validation, stale run recovery).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import update

from app.config import get_settings
from app.database import async_session_factory

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    """
    On startup: validate env config, recover stale runs.
    """
    settings = get_settings()
    logger.info("app_starting", env=settings.env)

    # Crash recovery: mark stale discovery runs as failed
    try:
        from app.models.ci_models import CIRun

        async with async_session_factory() as session:
            threshold = datetime.now(timezone.utc) - timedelta(minutes=30)
            result = await session.execute(
                update(CIRun)
                .where(
                    CIRun.status.notin_(["complete", "failed"]),
                    CIRun.updated_at < threshold,
                )
                .values(
                    status="failed",
                    error_message="Server restarted during pipeline execution",
                )
            )
            if result.rowcount > 0:  # type: ignore[union-attr]
                await session.commit()
                logger.warning("stale_runs_recovered", count=result.rowcount)
    except Exception as e:
        # Don't block startup if stale check fails (table may not exist yet)
        logger.warning("stale_run_check_skipped", error=str(e))

    yield

    logger.info("app_shutting_down")


app = FastAPI(
    title="Soft-Cases API",
    description="Citation Intelligence — authoritative source discovery for Claim Sets",
    version="0.1.0",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
from app.citation_intel.router import router as citation_intel_router

app.include_router(citation_intel_router, prefix="/api/v1")
