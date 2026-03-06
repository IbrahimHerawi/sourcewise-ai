"""FastAPI application entrypoint."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.core.logging import RequestCorrelationIdMiddleware, setup_logging
from app.core.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle hooks."""
    settings = get_settings()
    setup_logging(settings.log_level)
    logger = logging.getLogger(__name__)
    logger.info("Application startup complete")

    # Placeholder: initialize workers or background services.
    yield
    # Placeholder: gracefully stop workers or background services.

    logger.info("Application shutdown complete")


settings = get_settings()

app = FastAPI(
    title=settings.app_title,
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(RequestCorrelationIdMiddleware)
app.include_router(api_router)
