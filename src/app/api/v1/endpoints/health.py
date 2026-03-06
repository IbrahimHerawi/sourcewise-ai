"""V1 health check endpoints."""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response schema."""

    status: str


@router.get("", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Liveness endpoint."""
    return HealthResponse(status="ok")
