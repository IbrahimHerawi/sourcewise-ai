"""API v1 endpoint modules."""

from app.api.v1.endpoints.documents import router as documents_router
from app.api.v1.endpoints.health import router as health_router

__all__ = ["documents_router", "health_router"]
