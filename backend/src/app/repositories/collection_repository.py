"""Owner-scoped repository for collection CRUD access."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.collections import CollectionCreateRequest, CollectionUpdateRequest
from app.db.models.collections import Collection

CASE_INSENSITIVE_NAME_INDEX = "uq_collections_user_lower_name"


class DuplicateCollectionNameError(ValueError):
    """Raised when one owner already has a collection with the same name."""

    def __init__(self, user_id: uuid.UUID, name: str) -> None:
        super().__init__("A collection with this name already exists.")
        self.user_id = user_id
        self.name = name


class CollectionRepository:
    """Data access methods for user-owned collections."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_collection(
        self,
        user_id: uuid.UUID,
        name: str,
        description: str | None = None,
    ) -> Collection:
        """Create a normalized collection for an owner."""
        request = CollectionCreateRequest(name=name, description=description)
        stmt = (
            insert(Collection)
            .values(
                user_id=user_id,
                name=request.name,
                description=request.description,
            )
            .on_conflict_do_nothing(
                index_elements=[Collection.user_id, func.lower(Collection.name)]
            )
            .returning(Collection)
        )
        collection = await self._session.scalar(stmt)
        if collection is None:
            raise DuplicateCollectionNameError(user_id, request.name)
        return collection

    async def list_collections(
        self,
        user_id: uuid.UUID,
        limit: int,
        offset: int,
    ) -> list[Collection]:
        """Return one owner's collections ordered from newest to oldest."""
        self._validate_pagination(limit=limit, offset=offset)
        stmt = (
            select(Collection)
            .where(Collection.user_id == user_id)
            .order_by(Collection.created_at.desc(), Collection.id.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.scalars(stmt)
        return list(result.all())

    async def count_collections(self, user_id: uuid.UUID) -> int:
        """Return the number of collections owned by a user."""
        stmt = (
            select(func.count())
            .select_from(Collection)
            .where(Collection.user_id == user_id)
        )
        total = await self._session.scalar(stmt)
        return int(total or 0)

    async def get_collection(
        self,
        user_id: uuid.UUID,
        collection_id: uuid.UUID,
    ) -> Collection | None:
        """Get an owner-scoped collection by primary key."""
        stmt = select(Collection).where(
            Collection.user_id == user_id,
            Collection.id == collection_id,
        )
        return await self._session.scalar(stmt)

    async def update_collection(
        self,
        user_id: uuid.UUID,
        collection_id: uuid.UUID,
        **supplied_fields: object,
    ) -> Collection | None:
        """Normalize and update explicitly supplied collection fields."""
        request = CollectionUpdateRequest.model_validate(supplied_fields)
        values = request.model_dump(exclude_unset=True)
        stmt = (
            update(Collection)
            .where(
                Collection.user_id == user_id,
                Collection.id == collection_id,
            )
            .values(**values, updated_at=func.now())
            .returning(Collection)
        )

        try:
            async with self._session.begin_nested():
                return await self._session.scalar(stmt)
        except IntegrityError as exc:
            if self._violates_collection_name_index(exc):
                duplicate_name = request.name
                assert duplicate_name is not None
                raise DuplicateCollectionNameError(user_id, duplicate_name) from exc
            raise

    async def delete_collection(
        self,
        user_id: uuid.UUID,
        collection_id: uuid.UUID,
    ) -> bool:
        """Delete an owner-scoped collection and report whether it existed."""
        stmt = (
            delete(Collection)
            .where(
                Collection.user_id == user_id,
                Collection.id == collection_id,
            )
            .returning(Collection.id)
        )
        deleted_id = await self._session.scalar(stmt)
        return deleted_id is not None

    @staticmethod
    def _validate_pagination(*, limit: int, offset: int) -> None:
        if limit <= 0:
            raise ValueError("limit must be greater than 0")
        if offset < 0:
            raise ValueError("offset must be greater than or equal to 0")

    @staticmethod
    def _violates_collection_name_index(exc: IntegrityError) -> bool:
        cause: BaseException | None = exc
        while cause is not None:
            if getattr(cause, "constraint_name", None) == CASE_INSENSITIVE_NAME_INDEX:
                return True
            cause = cause.__cause__
        return False


__all__ = ["CollectionRepository", "DuplicateCollectionNameError"]
