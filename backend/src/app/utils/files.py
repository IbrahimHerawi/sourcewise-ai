"""Streaming file upload validation and atomic storage helpers."""

from __future__ import annotations

import codecs
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final
from uuid import UUID

from fastapi import UploadFile

from app.core.settings import get_settings


class UploadValidationError(ValueError):
    """Raised when an upload fails filename, size, or content validation."""


class SupportedUploadExtension(StrEnum):
    """Allowed upload file extensions."""

    TXT = ".txt"
    MD = ".md"
    PDF = ".pdf"


@dataclass(frozen=True, slots=True)
class StoredUpload:
    """Server-derived metadata for a validated, atomically stored upload."""

    filename: str
    original_extension: str
    content_type: str
    size_bytes: int
    storage_path: str


ALLOWED_UPLOAD_EXTENSIONS: Final[frozenset[str]] = frozenset(
    extension.value for extension in SupportedUploadExtension
)

_CONTENT_TYPES: Final[dict[str, str]] = {
    SupportedUploadExtension.TXT.value: "text/plain",
    SupportedUploadExtension.MD.value: "text/markdown",
    SupportedUploadExtension.PDF.value: "application/pdf",
}
_BYTES_PER_MB: Final[int] = 1024 * 1024
_CHUNK_SIZE: Final[int] = 64 * 1024
_PDF_HEADER_WINDOW: Final[int] = 1024
_PDF_SIGNATURE: Final[bytes] = b"%PDF-"


async def save_validated_upload(upload: UploadFile, document_id: UUID) -> StoredUpload:
    """Stream, validate, and atomically store one upload under its document UUID."""

    filename = _sanitize_filename(upload.filename or "")
    original_extension = Path(filename).suffix.lower()
    if original_extension not in ALLOWED_UPLOAD_EXTENSIONS:
        raise UploadValidationError(
            "Unsupported file extension. Allowed extensions are: .txt, .md, .pdf."
        )

    settings = get_settings()
    max_size_bytes = settings.max_upload_mb * _BYTES_PER_MB
    upload_root = Path(settings.upload_root_dir).expanduser().resolve(strict=False)
    target_dir = _resolve_under_root(upload_root, upload_root / str(document_id))
    storage_path = _resolve_under_root(target_dir, target_dir / filename)
    part_path = _resolve_under_root(target_dir, target_dir / f"{filename}.part")

    target_dir_created = False
    try:
        upload_root.mkdir(parents=True, exist_ok=True)
        target_dir_created = not target_dir.exists()
        target_dir.mkdir(parents=False, exist_ok=True)

        # Resolve again after directory creation so an existing link cannot redirect writes.
        target_dir = _resolve_under_root(upload_root, target_dir)
        storage_path = _resolve_under_root(upload_root, target_dir / filename)
        part_path = _resolve_under_root(upload_root, target_dir / f"{filename}.part")

        size_bytes = await _stream_to_part_file(
            upload,
            part_path=part_path,
            original_extension=original_extension,
            max_size_bytes=max_size_bytes,
            max_upload_mb=settings.max_upload_mb,
        )
        part_path.replace(storage_path)
    except BaseException:
        _remove_partial_upload(
            upload_root=upload_root,
            part_path=part_path,
            target_dir=target_dir,
            remove_target_dir=target_dir_created,
        )
        raise

    return StoredUpload(
        filename=filename,
        original_extension=original_extension,
        content_type=_CONTENT_TYPES[original_extension],
        size_bytes=size_bytes,
        storage_path=str(storage_path),
    )


async def _stream_to_part_file(
    upload: UploadFile,
    *,
    part_path: Path,
    original_extension: str,
    max_size_bytes: int,
    max_upload_mb: int,
) -> int:
    size_bytes = 0
    pdf_prefix = bytearray()
    utf8_decoder = None
    if original_extension in {
        SupportedUploadExtension.TXT.value,
        SupportedUploadExtension.MD.value,
    }:
        utf8_decoder = codecs.getincrementaldecoder("utf-8")(errors="strict")

    with part_path.open("wb") as part_file:
        while chunk := await upload.read(_CHUNK_SIZE):
            size_bytes += len(chunk)
            if size_bytes > max_size_bytes:
                raise UploadValidationError(
                    f"Upload exceeds MAX_UPLOAD_MB ({max_upload_mb} MB)."
                )

            if utf8_decoder is not None:
                _validate_text_chunk(chunk, utf8_decoder)
            elif len(pdf_prefix) < _PDF_HEADER_WINDOW:
                remaining = _PDF_HEADER_WINDOW - len(pdf_prefix)
                pdf_prefix.extend(chunk[:remaining])

            part_file.write(chunk)

        if size_bytes == 0:
            raise UploadValidationError("Upload must not be empty.")

        if utf8_decoder is not None:
            _finish_utf8_validation(utf8_decoder)
        elif _PDF_SIGNATURE not in pdf_prefix:
            raise UploadValidationError(
                "PDF content is invalid: %PDF- was not found within the first 1,024 bytes."
            )

    return size_bytes


def _validate_text_chunk(
    chunk: bytes,
    decoder: codecs.IncrementalDecoder,
) -> None:
    if b"\x00" in chunk:
        raise UploadValidationError("TXT and MD uploads must not contain NUL bytes.")
    try:
        decoder.decode(chunk, final=False)
    except UnicodeDecodeError as exc:
        raise UploadValidationError("TXT and MD uploads must contain valid UTF-8.") from exc


def _finish_utf8_validation(decoder: codecs.IncrementalDecoder) -> None:
    try:
        decoder.decode(b"", final=True)
    except UnicodeDecodeError as exc:
        raise UploadValidationError("TXT and MD uploads must contain valid UTF-8.") from exc


def _resolve_under_root(upload_root: Path, candidate: Path) -> Path:
    resolved_root = upload_root.resolve(strict=False)
    resolved_candidate = candidate.resolve(strict=False)
    if not resolved_candidate.is_relative_to(resolved_root):
        raise UploadValidationError("Upload storage path must remain under UPLOAD_ROOT_DIR.")
    return resolved_candidate


def _remove_partial_upload(
    *,
    upload_root: Path,
    part_path: Path,
    target_dir: Path,
    remove_target_dir: bool,
) -> None:
    try:
        safe_part_path = _resolve_under_root(upload_root, part_path)
        safe_part_path.unlink(missing_ok=True)
    except (OSError, UploadValidationError):
        pass

    if remove_target_dir:
        try:
            safe_target_dir = _resolve_under_root(upload_root, target_dir)
            safe_target_dir.rmdir()
        except (OSError, UploadValidationError):
            pass


def _sanitize_filename(filename: str) -> str:
    """Keep the original file basename while avoiding path traversal."""

    if "\x00" in filename:
        raise UploadValidationError("Filename is invalid.")
    safe_filename = Path(filename).name.strip()
    if not safe_filename:
        raise UploadValidationError("Filename is required.")
    return safe_filename
