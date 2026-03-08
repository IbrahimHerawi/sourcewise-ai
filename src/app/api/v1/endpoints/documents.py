"""V1 document upload and retrieval endpoints."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.documents import (
    DocumentDetailsResponse,
    DocumentSummaryResponse,
    DocumentUploadRequest,
    DocumentUploadResponse,
    PaginatedDocumentListResponse,
)
from app.core.errors import (
    AppError,
    ExternalServiceError,
    IngestionError,
    NotFoundError,
    ValidationError,
)
from app.db.models.documents import DocumentStatus
from app.db.models.ingestion_jobs import IngestionJobStatus
from app.db.session import get_db_session
from app.repositories.document_repository import DocumentRepository
from app.repositories.ingestion_job_repository import IngestionJobRepository
from app.utils.files import (
    TextExtractionError,
    UploadValidationError,
    extract_text,
    save_upload_to_disk,
    validate_upload,
)
from app.workers.ingestion import IngestionManager

logger = logging.getLogger(__name__)

router = APIRouter()


async def _build_upload_request(
    file: Annotated[UploadFile | None, File(description="Document file (.txt, .md, .pdf)")] = None,
) -> DocumentUploadRequest:
    if file is None:
        raise ValidationError(
            "Multipart field 'file' is required.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return DocumentUploadRequest(file=file)


def _get_ingestion_manager(request: Request) -> IngestionManager:
    ingestion_manager = getattr(request.app.state, "ingestion_manager", None)
    if not isinstance(ingestion_manager, IngestionManager):
        raise IngestionError(
            "Ingestion manager is not available.",
            code="ingestion_unavailable",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return ingestion_manager


def _upload_exception(error: UploadValidationError | TextExtractionError) -> ValidationError:
    message = str(error)
    if "MAX_UPLOAD_MB" in message:
        return ValidationError(message, status_code=status.HTTP_413_CONTENT_TOO_LARGE)
    return ValidationError(message, status_code=status.HTTP_400_BAD_REQUEST)


def _cleanup_saved_file(storage_path: str) -> None:
    path = Path(storage_path)
    try:
        if path.exists():
            path.unlink()
        if path.parent.exists() and not any(path.parent.iterdir()):
            path.parent.rmdir()
    except OSError:
        logger.warning("Failed to cleanup upload file after persistence error: %s", storage_path)


@router.get("", response_model=PaginatedDocumentListResponse)
async def list_documents(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PaginatedDocumentListResponse:
    """Return paginated document summaries ordered from newest to oldest."""
    document_repo = DocumentRepository(session)
    items = await document_repo.list_documents(limit=limit, offset=offset)
    total = await document_repo.count_documents()

    return PaginatedDocumentListResponse(
        items=[DocumentSummaryResponse.model_validate(document) for document in items],
        limit=limit,
        offset=offset,
        total=total,
    )


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    payload: Annotated[DocumentUploadRequest, Depends(_build_upload_request)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    ingestion_manager: Annotated[IngestionManager, Depends(_get_ingestion_manager)],
) -> DocumentUploadResponse:
    """Upload one document, persist metadata, create a pending job, and enqueue ingestion."""
    upload_file = payload.file
    filename = Path(upload_file.filename or "").name.strip()
    if not filename:
        raise ValidationError(
            "Filename is required.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    file_bytes = await upload_file.read()
    try:
        extension = validate_upload(
            filename=filename,
            content_type=upload_file.content_type,
            size_bytes=len(file_bytes),
        )
        extracted_text = extract_text(extension, file_bytes)
    except (UploadValidationError, TextExtractionError) as exc:
        raise _upload_exception(exc) from exc

    document_id = uuid.uuid4()
    try:
        storage_path = save_upload_to_disk(document_id, filename, file_bytes)
    except UploadValidationError as exc:
        raise ValidationError(
            str(exc),
            status_code=status.HTTP_400_BAD_REQUEST,
        ) from exc
    except OSError as exc:
        logger.exception("Failed to persist uploaded file for document %s.", document_id)
        raise ExternalServiceError(
            "Failed to persist uploaded file.",
            code="file_persistence_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        ) from exc
    finally:
        await upload_file.close()

    document_repo = DocumentRepository(session)
    job_repo = IngestionJobRepository(session)

    try:
        async with session.begin():
            document = await document_repo.create_document(
                id=document_id,
                filename=filename,
                original_extension=extension,
                content_type=upload_file.content_type or "application/octet-stream",
                size_bytes=len(file_bytes),
                storage_path=storage_path,
                extracted_text=extracted_text,
                status=DocumentStatus.PENDING,
            )
            job = await job_repo.create_job(
                document_id=document.id,
                status=IngestionJobStatus.PENDING,
            )
    except Exception as exc:
        _cleanup_saved_file(storage_path)
        logger.exception("Failed to persist document and ingestion job for %s.", document_id)
        raise AppError(
            "Failed to persist document metadata.",
            code="internal_server_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        ) from exc

    try:
        await ingestion_manager.enqueue(job_id=job.id)
    except RuntimeError as exc:
        logger.exception("Failed to enqueue ingestion job %s.", job.id)
        raise IngestionError(
            "Ingestion manager is not running.",
            code="ingestion_unavailable",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        ) from exc

    return DocumentUploadResponse(
        document_id=document.id,
        filename=document.filename,
        status=document.status,
    )

@router.get("/{document_id:uuid}", response_model=DocumentDetailsResponse)
async def get_document(
    document_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DocumentDetailsResponse:
    """Return one document metadata row."""
    document_repo = DocumentRepository(session)
    document = await document_repo.get_document(document_id)
    if document is None:
        raise NotFoundError("Document not found.")

    return DocumentDetailsResponse(
        id=document.id,
        filename=document.filename,
        status=document.status,
        created_at=document.created_at,
        updated_at=document.updated_at,
        error_message=document.error_message,
        text_length=len(document.extracted_text),
    )
