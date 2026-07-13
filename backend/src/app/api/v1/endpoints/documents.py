"""V1 document upload and retrieval endpoints."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_verified_user
from app.api.schemas.documents import (
    DocumentDetailsResponse,
    DocumentSummaryResponse,
    DocumentUploadItemResponse,
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
from app.db.models.auth import User
from app.db.models.documents import DocumentStatus
from app.db.models.ingestion_jobs import IngestionJobStatus
from app.db.session import get_db_session
from app.repositories.collection_repository import CollectionRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.ingestion_job_repository import IngestionJobRepository
from app.utils.files import StoredUpload, UploadValidationError, save_validated_upload
from app.workers.ingestion import IngestionManager

logger = logging.getLogger(__name__)

router = APIRouter()


async def _build_upload_request(
    files: Annotated[
        list[UploadFile] | None,
        File(description="One to three document files (.txt, .md, .pdf)"),
    ] = None,
    collection_id: Annotated[uuid.UUID | None, Form()] = None,
) -> DocumentUploadRequest:
    uploads = files or []
    if not 1 <= len(uploads) <= 3:
        await _close_uploads(uploads)
        raise ValidationError(
            "Multipart field 'files' must contain between 1 and 3 files.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return DocumentUploadRequest(files=uploads, collection_id=collection_id)


async def _close_uploads(uploads: list[UploadFile]) -> None:
    for upload in uploads:
        try:
            await upload.close()
        except Exception:
            logger.warning("Failed to close an upload file handle.")


def _get_ingestion_manager(request: Request) -> IngestionManager:
    ingestion_manager = getattr(request.app.state, "ingestion_manager", None)
    if not isinstance(ingestion_manager, IngestionManager):
        raise IngestionError(
            "Ingestion manager is not available.",
            code="ingestion_unavailable",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return ingestion_manager


def _upload_exception(error: UploadValidationError) -> ValidationError:
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
        logger.warning("Failed to clean up a staged upload file.")


def _cleanup_saved_files(staged_uploads: list[tuple[uuid.UUID, StoredUpload]]) -> None:
    for _, stored_upload in staged_uploads:
        _cleanup_saved_file(stored_upload.storage_path)


@router.get("", response_model=PaginatedDocumentListResponse)
async def list_documents(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_verified_user)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    collection_id: Annotated[uuid.UUID | None, Query()] = None,
) -> PaginatedDocumentListResponse:
    """Return paginated document summaries ordered from newest to oldest."""
    if collection_id is not None:
        collection = await CollectionRepository(session).get_collection(
            current_user.id,
            collection_id,
        )
        if collection is None:
            raise NotFoundError("Collection not found.")

    document_repo = DocumentRepository(session)
    items = await document_repo.list_documents(
        current_user.id,
        limit=limit,
        offset=offset,
        collection_id=collection_id,
    )
    total = await document_repo.count_documents(
        current_user.id,
        collection_id=collection_id,
    )

    return PaginatedDocumentListResponse(
        items=[DocumentSummaryResponse.model_validate(document) for document in items],
        limit=limit,
        offset=offset,
        total=total,
    )


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_documents(
    request: Request,
    current_user: Annotated[User, Depends(get_current_verified_user)],
    payload: Annotated[DocumentUploadRequest, Depends(_build_upload_request)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DocumentUploadResponse:
    """Accept an authenticated, all-or-nothing upload batch for ingestion."""
    staged_uploads: list[tuple[uuid.UUID, StoredUpload]] = []
    documents = []
    jobs = []
    try:
        user_id = current_user.id
        if payload.collection_id is not None:
            collection = await CollectionRepository(session).get_collection(
                user_id,
                payload.collection_id,
            )
            if collection is None:
                raise NotFoundError("Collection not found.")

        # Authentication and ownership checks open a read transaction. End it before
        # streaming files so the persistence transaction remains short.
        await session.commit()

        try:
            for upload_file in payload.files:
                document_id = uuid.uuid4()
                stored_upload = await save_validated_upload(upload_file, document_id)
                staged_uploads.append((document_id, stored_upload))
        except BaseException as exc:
            _cleanup_saved_files(staged_uploads)
            if isinstance(exc, UploadValidationError):
                raise _upload_exception(exc) from exc
            if isinstance(exc, OSError):
                logger.exception("Failed to stage an upload batch.")
                raise ExternalServiceError(
                    "Failed to persist uploaded file.",
                    code="file_persistence_error",
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                ) from exc
            raise

        document_repo = DocumentRepository(session)
        job_repo = IngestionJobRepository(session)
        try:
            async with session.begin():
                for document_id, stored_upload in staged_uploads:
                    document = await document_repo.create_document(
                        user_id,
                        collection_id=payload.collection_id,
                        id=document_id,
                        filename=stored_upload.filename,
                        original_extension=stored_upload.original_extension,
                        content_type=stored_upload.content_type,
                        size_bytes=stored_upload.size_bytes,
                        storage_path=stored_upload.storage_path,
                        extracted_text=None,
                        status=DocumentStatus.PENDING,
                        error_message=None,
                    )
                    job = await job_repo.create_job(
                        document_id=document.id,
                        status=IngestionJobStatus.PENDING,
                        error_message=None,
                    )
                    documents.append(document)
                    jobs.append(job)
        except BaseException as exc:
            _cleanup_saved_files(staged_uploads)
            if not isinstance(exc, Exception):
                raise
            logger.exception("Failed to persist an upload batch.")
            raise AppError(
                "Failed to persist document metadata.",
                code="internal_server_error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from exc
    finally:
        await _close_uploads(payload.files)

    enqueue_failed = False
    try:
        ingestion_manager = _get_ingestion_manager(request)
    except IngestionError:
        ingestion_manager = None
        enqueue_failed = True

    if ingestion_manager is not None:
        for job in jobs:
            try:
                await ingestion_manager.enqueue(job_id=job.id)
            except Exception:
                enqueue_failed = True
    if enqueue_failed:
        logger.warning(
            "One or more committed ingestion jobs could not be enqueued; "
            "startup recovery will retry them."
        )

    return DocumentUploadResponse(
        items=[
            DocumentUploadItemResponse(
                document_id=document.id,
                filename=document.filename,
                collection_id=document.collection_id,
                status=document.status,
            )
            for document in documents
        ]
    )


@router.get("/{document_id:uuid}", response_model=DocumentDetailsResponse)
async def get_document(
    document_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_verified_user)],
) -> DocumentDetailsResponse:
    """Return one document metadata row."""
    document_repo = DocumentRepository(session)
    document = await document_repo.get_document(current_user.id, document_id)
    if document is None:
        raise NotFoundError("Document not found.")

    return DocumentDetailsResponse.model_validate(document)
