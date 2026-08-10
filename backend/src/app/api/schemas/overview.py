"""Response schema for the authenticated user overview."""

from pydantic import BaseModel, NonNegativeInt


class OverviewResponse(BaseModel):
    """Owner-scoped resource totals for the authenticated user."""

    total_documents: NonNegativeInt
    total_questions: NonNegativeInt
    total_collections: NonNegativeInt


__all__ = ["OverviewResponse"]
