"""Schemas for collection management endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    StringConstraints,
    field_validator,
    model_validator,
)

CollectionName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]
CollectionDescription = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=2_000),
]


class CollectionCreateRequest(BaseModel):
    """Request payload for creating a collection."""

    model_config = ConfigDict(extra="forbid")

    name: CollectionName
    description: CollectionDescription | None = None

    @field_validator("description", mode="after")
    @classmethod
    def normalize_empty_description(cls, value: str | None) -> str | None:
        """Represent blank descriptions consistently as null."""
        return value or None


class CollectionUpdateRequest(BaseModel):
    """Request payload for updating at least one collection field."""

    model_config = ConfigDict(extra="forbid")

    name: CollectionName | None = None
    description: CollectionDescription | None = None

    @field_validator("name", mode="before")
    @classmethod
    def reject_null_name(cls, value: Any) -> Any:
        """Allow omission, but prevent clearing the required collection name."""
        if value is None:
            raise ValueError("name cannot be null")
        return value

    @field_validator("description", mode="after")
    @classmethod
    def normalize_empty_description(cls, value: str | None) -> str | None:
        """Treat null or a blank description as an explicit clear operation."""
        return value or None

    @model_validator(mode="after")
    def reject_empty_update(self) -> CollectionUpdateRequest:
        """Require at least one explicitly supplied field."""
        if not self.model_fields_set:
            raise ValueError("at least one field must be provided")
        return self


class CollectionResponse(BaseModel):
    """API-safe collection response without owner details."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime


class PaginatedCollectionListResponse(BaseModel):
    """Paginated collection list response payload."""

    model_config = ConfigDict(extra="forbid")

    items: list[CollectionResponse]
    limit: int
    offset: int
    total: int


__all__ = [
    "CollectionCreateRequest",
    "CollectionResponse",
    "CollectionUpdateRequest",
    "PaginatedCollectionListResponse",
]
