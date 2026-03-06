"""File upload validation, storage, and text extraction helpers."""

from __future__ import annotations

import re
from enum import StrEnum
from io import BytesIO
from pathlib import Path
from typing import Final
from uuid import UUID

from pypdf import PdfReader

from app.core.settings import get_settings


class UploadValidationError(ValueError):
    """Raised when upload metadata fails validation."""


class TextExtractionError(ValueError):
    """Raised when text extraction fails."""


class SupportedUploadExtension(StrEnum):
    """Allowed upload file extensions."""

    TXT = ".txt"
    MD = ".md"
    PDF = ".pdf"


ALLOWED_UPLOAD_EXTENSIONS: Final[frozenset[str]] = frozenset(
    extension.value for extension in SupportedUploadExtension
)
PDF_EMPTY_TEXT_ERROR_MESSAGE: Final[str] = (
    "PDF contains no extractable text. The file may be image-only or missing a text layer."
)

_BYTES_PER_MB: Final[int] = 1024 * 1024
_NULL_CHARS_PATTERN: Final[re.Pattern[str]] = re.compile(r"\x00+")


def validate_upload(filename: str, content_type: str | None, size_bytes: int) -> str:
    """Validate an upload and return the normalized extension."""

    _ = content_type

    safe_filename = _sanitize_filename(filename)
    ext = Path(safe_filename).suffix.lower()

    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        raise UploadValidationError(
            "Unsupported file extension. Allowed extensions are: .txt, .md, .pdf."
        )

    if size_bytes < 0:
        raise UploadValidationError("Upload size cannot be negative.")

    settings = get_settings()
    max_size_bytes = settings.max_upload_mb * _BYTES_PER_MB
    if size_bytes > max_size_bytes:
        raise UploadValidationError(
            f"Upload exceeds MAX_UPLOAD_MB ({settings.max_upload_mb} MB)."
        )

    return ext


def save_upload_to_disk(document_id: UUID | str, filename: str, bytes: bytes) -> str:
    """Persist uploaded bytes to disk and return the storage path."""

    safe_filename = _sanitize_filename(filename)
    settings = get_settings()
    target_dir = Path(settings.upload_root_dir) / str(document_id)
    target_dir.mkdir(parents=True, exist_ok=True)

    storage_path = target_dir / safe_filename
    storage_path.write_bytes(bytes)
    return str(storage_path)


def extract_text(ext: str, bytes: bytes) -> str:
    """Extract text from supported file bytes and normalize the output."""

    normalized_ext = ext.lower()

    if normalized_ext not in ALLOWED_UPLOAD_EXTENSIONS:
        raise TextExtractionError(f"Unsupported extension for extraction: {ext}")

    if normalized_ext in (
        SupportedUploadExtension.TXT.value,
        SupportedUploadExtension.MD.value,
    ):
        extracted_text = bytes.decode("utf-8", errors="replace")
    else:
        extracted_text = _extract_pdf_text(bytes)

    return _normalize_extracted_text(extracted_text)


def _extract_pdf_text(bytes: bytes) -> str:
    """Extract text from PDF bytes using pypdf (text layer only, no OCR)."""

    try:
        pdf = PdfReader(BytesIO(bytes))
    except Exception as exc:
        raise TextExtractionError(f"Failed to read PDF: {exc}") from exc

    page_texts: list[str] = []
    for page in pdf.pages:
        page_texts.append(page.extract_text() or "")

    return "\n".join(page_texts)


def _normalize_extracted_text(text: str) -> str:
    """Apply light normalization to extracted text."""

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return _NULL_CHARS_PATTERN.sub("", normalized)


def _sanitize_filename(filename: str) -> str:
    """Keep the original file basename while avoiding path traversal."""

    safe_filename = Path(filename).name.strip()
    if not safe_filename:
        raise UploadValidationError("Filename is required.")
    return safe_filename
