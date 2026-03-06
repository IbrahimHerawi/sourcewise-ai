from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.utils import files


def _patch_settings(
    monkeypatch: pytest.MonkeyPatch,
    *,
    max_upload_mb: int = 10,
    upload_root_dir: str = "/tmp/uploads",
) -> None:
    monkeypatch.setattr(
        files,
        "get_settings",
        lambda: SimpleNamespace(
            max_upload_mb=max_upload_mb,
            upload_root_dir=upload_root_dir,
        ),
    )


@pytest.mark.parametrize(
    ("filename", "expected_ext"),
    [
        ("notes.txt", ".txt"),
        ("notes.md", ".md"),
        ("notes.pdf", ".pdf"),
        ("NOTES.TXT", ".txt"),
    ],
)
def test_validate_upload_accepts_supported_extensions(
    monkeypatch: pytest.MonkeyPatch,
    filename: str,
    expected_ext: str,
) -> None:
    _patch_settings(monkeypatch, max_upload_mb=10)

    ext = files.validate_upload(filename, "application/octet-stream", size_bytes=10)

    assert ext == expected_ext


@pytest.mark.parametrize("filename", ["notes.csv", "notes.docx", "notes.exe", "notes"])
def test_validate_upload_rejects_unsupported_extensions(
    monkeypatch: pytest.MonkeyPatch, filename: str
) -> None:
    _patch_settings(monkeypatch, max_upload_mb=10)

    with pytest.raises(files.UploadValidationError, match="Unsupported file extension"):
        files.validate_upload(filename, "application/octet-stream", size_bytes=10)


def test_validate_upload_rejects_size_over_max_upload_mb(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_settings(monkeypatch, max_upload_mb=1)
    over_limit_size = (1 * 1024 * 1024) + 1

    with pytest.raises(files.UploadValidationError, match="MAX_UPLOAD_MB"):
        files.validate_upload("notes.txt", "text/plain", size_bytes=over_limit_size)


@pytest.mark.parametrize("ext", [".txt", ".md"])
def test_extract_text_decodes_utf8_and_replaces_invalid_bytes(ext: str) -> None:
    raw_bytes = b"valid utf-8 \xe2\x9c\x93 and invalid \xff then \xc3("

    extracted = files.extract_text(ext, raw_bytes)

    assert extracted == raw_bytes.decode("utf-8", errors="replace")
    assert "\ufffd" in extracted


def test_extract_text_pdf_uses_fixture_and_returns_page_text() -> None:
    fixture_path = Path(__file__).parent / "assets" / "sample.pdf"
    pdf_bytes = fixture_path.read_bytes()

    extracted = files.extract_text(".pdf", pdf_bytes)

    assert "Sample PDF fixture text." in extracted


def test_save_upload_to_disk_writes_file_and_returns_stable_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_settings(monkeypatch, upload_root_dir=str(tmp_path))
    document_id = uuid4()

    first_path = files.save_upload_to_disk(document_id, "note.txt", b"first")
    second_path = files.save_upload_to_disk(document_id, "note.txt", b"second")

    assert first_path == second_path
    saved_path = Path(first_path)
    assert saved_path.exists()
    assert saved_path.read_bytes() == b"second"
    assert saved_path.parent == tmp_path / str(document_id)
