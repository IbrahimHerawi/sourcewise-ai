"""Top-level API router with version registration."""

from fastapi import APIRouter

from app.api.v1.endpoints.documents import router as documents_router
from app.api.v1.endpoints.questions import router as questions_router
from app.api.v1.router import router as v1_router

api_router = APIRouter(prefix="/api")
api_router.include_router(documents_router, prefix="/documents", include_in_schema=False)
api_router.include_router(questions_router, prefix="/questions", include_in_schema=False)
api_router.include_router(v1_router, prefix="/v1")
