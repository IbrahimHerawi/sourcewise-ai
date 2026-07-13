from __future__ import annotations

from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from app.utils import files


def _patch_settings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    max_upload_mb: int = 10,
) -> None:
    monkeypatch.setattr(
        files,
        "get_settings",
        lambda: SimpleNamespace(
            max_upload_mb=max_upload_mb,
            upload_root_dir=str(tmp_path),
        ),
    )


def _upload(
    filename: str,
    content: bytes,
    *,
    content_type: str = "application/octet-stream",
) -> UploadFile:
    return UploadFile(
        file=BytesIO(content),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("filename", "expected_extension", "expected_content_type"),
    [
        ("notes.txt", ".txt", "text/plain"),
        ("notes.MD", ".md", "text/markdown"),
        ("report.PDF", ".pdf", "application/pdf"),
    ],
)
async def test_save_validated_upload_streams_supported_files_and_derives_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    filename: str,
    expected_extension: str,
    expected_content_type: str,
) -> None:
    _patch_settings(monkeypatch, tmp_path)
    content = b"%PDF-1.7\nbody" if expected_extension == ".pdf" else b"valid UTF-8 \xe2\x9c\x93"
    upload = _upload(filename, content, content_type="malicious/client-value")
    document_id = uuid4()
    upload.read = AsyncMock(wraps=upload.read)

    stored = await files.save_validated_upload(upload, document_id)

    assert stored == files.StoredUpload(
        filename=filename,
        original_extension=expected_extension,
        content_type=expected_content_type,
        size_bytes=len(content),
        storage_path=str((tmp_path / str(document_id) / filename).resolve()),
    )
    assert Path(stored.storage_path).read_bytes() == content
    assert upload.read.await_count >= 2
    assert all(call.args == (64 * 1024,) for call in upload.read.await_args_list)
    assert not list(tmp_path.rglob("*.part"))


@pytest.mark.asyncio
@pytest.mark.parametrize("filename", ["notes.csv", "notes.docx", "notes.exe", "notes"])
async def test_save_validated_upload_rejects_unsupported_extension_before_reading(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    filename: str,
) -> None:
    _patch_settings(monkeypatch, tmp_path)
    upload = _upload(filename, b"content")
    upload.read = AsyncMock(wraps=upload.read)

    with pytest.raises(files.UploadValidationError, match="Unsupported file extension"):
        await files.save_validated_upload(upload, uuid4())

    upload.read.assert_not_awaited()
    assert not any(tmp_path.iterdir())


@pytest.mark.asyncio
async def test_save_validated_upload_rejects_empty_file_and_removes_partial_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_settings(monkeypatch, tmp_path)
    document_id = uuid4()

    with pytest.raises(files.UploadValidationError, match="must not be empty"):
        await files.save_validated_upload(_upload("empty.txt", b""), document_id)

    assert not (tmp_path / str(document_id)).exists()
    assert not list(tmp_path.rglob("*.part"))


@pytest.mark.asyncio
async def test_save_validated_upload_stops_reading_as_soon_as_limit_is_exceeded(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_settings(monkeypatch, tmp_path, max_upload_mb=1)
    content = b"a" * ((1024 * 1024) + (2 * 64 * 1024))
    upload = _upload("too-large.txt", content)
    upload.read = AsyncMock(wraps=upload.read)
    document_id = uuid4()

    with pytest.raises(files.UploadValidationError, match="MAX_UPLOAD_MB"):
        await files.save_validated_upload(upload, document_id)

    assert upload.read.await_count == 17
    assert upload.file.tell() == (1024 * 1024) + (64 * 1024)
    assert upload.file.tell() < len(content)
    assert not (tmp_path / str(document_id)).exists()


@pytest.mark.asyncio
async def test_max_upload_mb_applies_separately_and_duplicate_names_use_uuid_directories(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_settings(monkeypatch, tmp_path, max_upload_mb=1)
    content = b"a" * (1024 * 1024)
    first_id = uuid4()
    second_id = uuid4()

    first = await files.save_validated_upload(_upload("same.txt", content), first_id)
    second = await files.save_validated_upload(_upload("same.txt", content), second_id)

    assert first.size_bytes == second.size_bytes == len(content)
    assert Path(first.storage_path).parent == (tmp_path / str(first_id)).resolve()
    assert Path(second.storage_path).parent == (tmp_path / str(second_id)).resolve()
    assert first.storage_path != second.storage_path


@pytest.mark.asyncio
async def test_text_utf8_validation_handles_multibyte_sequence_split_across_chunks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_settings(monkeypatch, tmp_path)
    content = (b"a" * ((64 * 1024) - 1)) + "€".encode() + b"tail"

    stored = await files.save_validated_upload(_upload("split.md", content), uuid4())

    assert Path(stored.storage_path).read_bytes() == content


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("filename", "content", "message"),
    [
        ("invalid.txt", b"valid then \xff", "valid UTF-8"),
        ("truncated.md", b"truncated \xe2\x82", "valid UTF-8"),
        ("nul.txt", b"text\x00more", "NUL bytes"),
    ],
)
async def test_text_content_validation_rejects_invalid_content_and_cleans_up(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    filename: str,
    content: bytes,
    message: str,
) -> None:
    _patch_settings(monkeypatch, tmp_path)
    document_id = uuid4()

    with pytest.raises(files.UploadValidationError, match=message):
        await files.save_validated_upload(_upload(filename, content), document_id)

    assert not (tmp_path / str(document_id)).exists()
    assert not list(tmp_path.rglob("*.part"))


@pytest.mark.asyncio
async def test_pdf_signature_may_appear_anywhere_in_first_1024_bytes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_settings(monkeypatch, tmp_path)
    content = (b"x" * 1019) + b"%PDF-" + b"body"

    stored = await files.save_validated_upload(_upload("report.pdf", content), uuid4())

    assert Path(stored.storage_path).read_bytes() == content


@pytest.mark.asyncio
async def test_pdf_signature_after_first_1024_bytes_is_rejected_and_cleaned_up(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_settings(monkeypatch, tmp_path)
    document_id = uuid4()
    content = (b"x" * 1024) + b"%PDF-1.7"

    with pytest.raises(files.UploadValidationError, match="first 1,024 bytes"):
        await files.save_validated_upload(_upload("report.pdf", content), document_id)

    assert not (tmp_path / str(document_id)).exists()
    assert not list(tmp_path.rglob("*.part"))


@pytest.mark.asyncio
async def test_upload_is_written_to_part_file_until_validation_completes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_settings(monkeypatch, tmp_path)
    document_id = uuid4()
    target_dir = tmp_path / str(document_id)
    observations: list[tuple[bool, bool, int]] = []
    chunks = iter((b"hello", b""))

    async def _read(size: int) -> bytes:
        observations.append(
            (
                (target_dir / "atomic.txt.part").exists(),
                (target_dir / "atomic.txt").exists(),
                size,
            )
        )
        return next(chunks)

    upload = SimpleNamespace(filename="atomic.txt", read=_read)

    stored = await files.save_validated_upload(upload, document_id)  # type: ignore[arg-type]

    assert observations == [(True, False, 64 * 1024), (True, False, 64 * 1024)]
    assert Path(stored.storage_path).read_bytes() == b"hello"
    assert not (target_dir / "atomic.txt.part").exists()


@pytest.mark.asyncio
async def test_stream_read_failure_removes_partial_file_and_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_settings(monkeypatch, tmp_path)
    document_id = uuid4()
    upload = SimpleNamespace(
        filename="broken.txt",
        read=AsyncMock(side_effect=[b"partial", OSError("read failed")]),
    )

    with pytest.raises(OSError, match="read failed"):
        await files.save_validated_upload(upload, document_id)  # type: ignore[arg-type]

    assert not (tmp_path / str(document_id)).exists()
    assert not list(tmp_path.rglob("*.part"))


@pytest.mark.asyncio
async def test_filename_traversal_is_reduced_to_basename_and_stays_under_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_settings(monkeypatch, tmp_path)
    document_id = uuid4()

    stored = await files.save_validated_upload(
        _upload("../../outside.txt", b"inside"),
        document_id,
    )

    expected = (tmp_path / str(document_id) / "outside.txt").resolve()
    assert stored.filename == "outside.txt"
    assert Path(stored.storage_path) == expected
    assert expected.is_relative_to(tmp_path.resolve())
    assert not (tmp_path.parent / "outside.txt").exists()


def test_resolve_under_root_rejects_escape(tmp_path: Path) -> None:
    root = tmp_path.resolve()

    with pytest.raises(files.UploadValidationError, match="UPLOAD_ROOT_DIR"):
        files._resolve_under_root(root, root.parent / "escape.txt")
