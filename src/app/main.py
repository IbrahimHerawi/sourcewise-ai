"""FastAPI application entrypoint."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.core.logging import RequestCorrelationIdMiddleware, setup_logging
from app.core.settings import get_settings
from app.services.embeddings import close_embeddings_client
from app.workers.ingestion import IngestionManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle hooks."""
    settings = get_settings()
    setup_logging(settings.log_level)
    logger = logging.getLogger(__name__)
    ingestion_manager = IngestionManager(settings=settings)
    app.state.ingestion_manager = ingestion_manager

    try:
        await ingestion_manager.start()
        logger.info("Application startup complete")
        yield
    finally:
        await ingestion_manager.stop()
        app.state.ingestion_manager = None
        await close_embeddings_client()
        logger.info("Application shutdown complete")


settings = get_settings()

app = FastAPI(
    title=settings.app_title,
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(RequestCorrelationIdMiddleware)
app.include_router(api_router)
