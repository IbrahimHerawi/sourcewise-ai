"""Authenticated user overview endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_verified_user
from app.api.schemas.overview import OverviewResponse
from app.db.models.auth import User
from app.db.session import get_db_session
from app.repositories.overview_repository import OverviewRepository

router = APIRouter()


@router.get("", response_model=OverviewResponse)
async def get_overview(
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_verified_user)],
) -> OverviewResponse:
    """Return current owner-scoped resource totals for the authenticated user."""
    counts = await OverviewRepository(session).get_counts(current_user.id)
    response.headers["Cache-Control"] = "private, no-store"
    return OverviewResponse(
        total_documents=counts.total_documents,
        total_questions=counts.total_questions,
        total_collections=counts.total_collections,
    )


__all__ = ["router"]
