"""Version 1 API router."""

from fastapi import APIRouter

from app.api.v1.endpoints.documents import router as documents_router
from app.api.v1.endpoints.health import router as health_router

router = APIRouter()
router.include_router(documents_router, prefix="/documents", tags=["documents"])
router.include_router(health_router, prefix="/health", tags=["health"])
