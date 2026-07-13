"""Schemas for document upload and retrieval endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import UploadFile
from pydantic import BaseModel, ConfigDict

from app.db.models.documents import DocumentStatus


class DocumentUploadRequest(BaseModel):
    """Parsed multipart upload request payload."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    files: list[UploadFile]
    collection_id: UUID | None = None


class DocumentUploadItemResponse(BaseModel):
    """One accepted document in a batch upload response."""

    document_id: UUID
    filename: str
    collection_id: UUID | None
    status: DocumentStatus


class DocumentUploadResponse(BaseModel):
    """Response payload for a successful document upload batch."""

    items: list[DocumentUploadItemResponse]


class DocumentSummaryResponse(BaseModel):
    """Safe document metadata for list responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    collection_id: UUID | None
    filename: str
    original_extension: str
    content_type: str
    size_bytes: int
    status: DocumentStatus
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class PaginatedDocumentListResponse(BaseModel):
    """Paginated document list response payload."""

    items: list[DocumentSummaryResponse]
    limit: int
    offset: int
    total: int


class DocumentDetailsResponse(DocumentSummaryResponse):
    """Safe metadata for one document without stored content or internals."""
