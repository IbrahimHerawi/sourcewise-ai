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

    file: UploadFile


class DocumentUploadResponse(BaseModel):
    """Response payload for successful document upload."""

    document_id: UUID
    filename: str
    status: DocumentStatus


class DocumentDetailsResponse(BaseModel):
    """Document metadata response without full extracted text payload."""

    id: UUID
    filename: str
    status: DocumentStatus
    created_at: datetime
    updated_at: datetime
    error_message: str | None
    text_length: int
