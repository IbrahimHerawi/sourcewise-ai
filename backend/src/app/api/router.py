"""Top-level API router with version registration."""

from fastapi import APIRouter

from app.api.v1.router import router as v1_router

api_router = APIRouter(prefix="/api")
# All business APIs must be versioned under /api/v1.
api_router.include_router(v1_router, prefix="/v1")
