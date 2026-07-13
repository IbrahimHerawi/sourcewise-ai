"""V1 endpoints for user-owned collection management."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_verified_user
from app.api.schemas.collections import (
    CollectionCreateRequest,
    CollectionResponse,
    CollectionUpdateRequest,
    PaginatedCollectionListResponse,
)
from app.core.errors import AppError, NotFoundError
from app.db.models.auth import User
from app.db.session import get_db_session
from app.repositories.collection_repository import (
    CollectionRepository,
    DuplicateCollectionNameError,
)

router = APIRouter()


def _duplicate_name_error() -> AppError:
    return AppError(
        "A collection with this name already exists.",
        code="conflict",
        status_code=status.HTTP_409_CONFLICT,
    )


def _not_found_error() -> NotFoundError:
    return NotFoundError("Collection not found.")


@router.post("", response_model=CollectionResponse, status_code=status.HTTP_201_CREATED)
async def create_collection(
    payload: CollectionCreateRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_verified_user)],
) -> CollectionResponse:
    """Create a collection owned by the authenticated user."""
    repository = CollectionRepository(session)
    try:
        collection = await repository.create_collection(
            current_user.id,
            payload.name,
            payload.description,
        )
    except DuplicateCollectionNameError as exc:
        raise _duplicate_name_error() from exc

    await session.commit()
    return CollectionResponse.model_validate(collection)


@router.get("", response_model=PaginatedCollectionListResponse)
async def list_collections(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_verified_user)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PaginatedCollectionListResponse:
    """Return the authenticated user's collections from newest to oldest."""
    repository = CollectionRepository(session)
    items = await repository.list_collections(current_user.id, limit, offset)
    total = await repository.count_collections(current_user.id)
    return PaginatedCollectionListResponse(
        items=[CollectionResponse.model_validate(collection) for collection in items],
        limit=limit,
        offset=offset,
        total=total,
    )


@router.get("/{collection_id:uuid}", response_model=CollectionResponse)
async def get_collection(
    collection_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_verified_user)],
) -> CollectionResponse:
    """Return one collection owned by the authenticated user."""
    collection = await CollectionRepository(session).get_collection(
        current_user.id,
        collection_id,
    )
    if collection is None:
        raise _not_found_error()
    return CollectionResponse.model_validate(collection)


@router.patch("/{collection_id:uuid}", response_model=CollectionResponse)
async def update_collection(
    collection_id: uuid.UUID,
    payload: CollectionUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_verified_user)],
) -> CollectionResponse:
    """Update one collection owned by the authenticated user."""
    try:
        collection = await CollectionRepository(session).update_collection(
            current_user.id,
            collection_id,
            **payload.model_dump(exclude_unset=True),
        )
    except DuplicateCollectionNameError as exc:
        raise _duplicate_name_error() from exc

    if collection is None:
        raise _not_found_error()

    await session.commit()
    return CollectionResponse.model_validate(collection)


@router.delete("/{collection_id:uuid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_collection(
    collection_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_verified_user)],
) -> Response:
    """Delete one collection without deleting its documents or questions."""
    deleted = await CollectionRepository(session).delete_collection(
        current_user.id,
        collection_id,
    )
    if not deleted:
        raise _not_found_error()

    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
