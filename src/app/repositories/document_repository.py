"""Repository for document CRUD access."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.documents import Document, DocumentStatus


class DocumentRepository:
    """Data access methods for document records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_document(
        self,
        *,
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

    async def list_documents(self, limit: int, offset: int) -> list[Document]:
        """Return documents ordered from newest to oldest."""
        self._validate_pagination(limit=limit, offset=offset)
        stmt = (
            select(Document)
            .order_by(Document.created_at.desc(), Document.id.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.scalars(stmt)
        return list(result.all())

    async def count_documents(self) -> int:
        """Return the total number of documents."""
        stmt = select(func.count()).select_from(Document)
        total = await self._session.scalar(stmt)
        return int(total or 0)

    async def get_document(self, id: uuid.UUID) -> Document | None:
        """Get one document by primary key."""
        return await self._session.get(Document, id)

    async def update_status(
        self,
        id: uuid.UUID,
        status: DocumentStatus,
        error_message: str | None = None,
    ) -> Document | None:
        """Update status and optional error message for a document."""
        document = await self.get_document(id)
        if document is None:
            return None

        document.status = status
        document.error_message = error_message
        await self._session.flush()
        await self._session.refresh(document)
        return document

    @staticmethod
    def _validate_pagination(*, limit: int, offset: int) -> None:
        if limit <= 0:
            raise ValueError("limit must be greater than 0")
        if offset < 0:
            raise ValueError("offset must be greater than or equal to 0")


__all__ = ["DocumentRepository"]
