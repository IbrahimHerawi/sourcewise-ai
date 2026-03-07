"""API request and response schemas."""

from app.api.schemas.documents import (
    DocumentDetailsResponse,
    DocumentSummaryResponse,
    DocumentUploadRequest,
    DocumentUploadResponse,
    PaginatedDocumentListResponse,
)

__all__ = [
    "DocumentDetailsResponse",
    "DocumentSummaryResponse",
    "DocumentUploadRequest",
    "DocumentUploadResponse",
    "PaginatedDocumentListResponse",
]
