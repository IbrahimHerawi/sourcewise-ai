"""Owner-scoped repository for document CRUD access."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, exists, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.selectable import Exists

from app.db.models.collections import Collection
from app.db.models.documents import Document, DocumentStatus


class DocumentRepository:
    """Data access methods for user-owned document records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_document(
        self,
        user_id: uuid.UUID,
        *,
        collection_id: uuid.UUID | None = None,
        id: uuid.UUID | None = None,
        filename: str,
        original_extension: str,
        content_type: str,
        size_bytes: int,
        storage_path: str,
        extracted_text: str,
        status: DocumentStatus = DocumentStatus.PENDING,
        error_message: str | None = None,
    ) -> Document:
        """Create and flush a document row."""
        document_kwargs: dict[str, object] = {}
        if id is not None:
            document_kwargs["id"] = id

        document = Document(
            user_id=user_id,
            collection_id=collection_id,
            filename=filename,
            original_extension=original_extension,
            content_type=content_type,
            size_bytes=size_bytes,
            storage_path=storage_path,
            extracted_text=extracted_text,
            status=status,
            error_message=error_message,
            **document_kwargs,
        )
        self._session.add(document)
        await self._session.flush()
        await self._session.refresh(document)
        return document

    async def list_documents(
        self,
        user_id: uuid.UUID,
        limit: int,
        offset: int,
        collection_id: uuid.UUID | None = None,
    ) -> list[Document]:
        """Return one owner's documents ordered from newest to oldest."""
        self._validate_pagination(limit=limit, offset=offset)
        stmt = (
            select(Document)
            .where(Document.user_id == user_id)
            .order_by(Document.created_at.desc(), Document.id.desc())
            .limit(limit)
            .offset(offset)
        )
        if collection_id is not None:
            stmt = stmt.where(
                Document.collection_id == collection_id,
                self._user_owns_collection(user_id, collection_id),
            )
        result = await self._session.scalars(stmt)
        return list(result.all())

    async def count_documents(
        self,
        user_id: uuid.UUID,
        collection_id: uuid.UUID | None = None,
    ) -> int:
        """Return the number of documents owned by a user."""
        stmt = (
            select(func.count())
            .select_from(Document)
            .where(Document.user_id == user_id)
        )
        if collection_id is not None:
            stmt = stmt.where(
                Document.collection_id == collection_id,
                self._user_owns_collection(user_id, collection_id),
            )
        total = await self._session.scalar(stmt)
        return int(total or 0)

    async def get_document(
        self,
        user_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> Document | None:
        """Get an owner-scoped document by primary key."""
        stmt = select(Document).where(
            Document.user_id == user_id,
            Document.id == document_id,
        )
        return await self._session.scalar(stmt)

    async def delete_document(
        self,
        user_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> Document | None:
        """Delete an owner-scoped document and return it when it existed."""
        stmt = (
            delete(Document)
            .where(
                Document.user_id == user_id,
                Document.id == document_id,
            )
            .returning(Document)
        )
        return await self._session.scalar(stmt)

    async def update_status(
        self,
        user_id: uuid.UUID,
        document_id: uuid.UUID,
        status: DocumentStatus,
        error_message: str | None = None,
    ) -> Document | None:
        """Update status and optional error message for an owner-scoped document."""
        stmt = (
            update(Document)
            .where(
                Document.user_id == user_id,
                Document.id == document_id,
            )
            .values(
                status=status,
                error_message=error_message,
                updated_at=func.now(),
            )
            .returning(Document)
        )
        return await self._session.scalar(stmt)

    @staticmethod
    def _user_owns_collection(
        user_id: uuid.UUID,
        collection_id: uuid.UUID,
    ) -> Exists:
        return exists(
            select(Collection.id).where(
                Collection.id == collection_id,
                Collection.user_id == user_id,
            )
        )

    @staticmethod
    def _validate_pagination(*, limit: int, offset: int) -> None:
        if limit <= 0:
            raise ValueError("limit must be greater than 0")
        if offset < 0:
            raise ValueError("offset must be greater than or equal to 0")


__all__ = ["DocumentRepository"]
