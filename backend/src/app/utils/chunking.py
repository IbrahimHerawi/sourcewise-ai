"""Deterministic text chunking and embedding-text preparation helpers."""

from __future__ import annotations

from typing import Final

from app.core.settings import get_settings

CHUNK_SIZE_CHARS: Final[int] = 2000
CHUNK_OVERLAP_CHARS: Final[int] = 100

_DOC_EMBEDDING_PREFIX: Final[str] = "search_document: "
_QUERY_EMBEDDING_PREFIX: Final[str] = "search_query: "


def _is_word_char(char: str) -> bool:
    return char.isalnum()


def _is_mid_word_boundary(text: str, index: int) -> bool:
    if index <= 0 or index >= len(text):
        return False
    return _is_word_char(text[index - 1]) and _is_word_char(text[index])


def _snap_end_to_word_boundary(text: str, start: int, end: int) -> int:
    if end >= len(text) or not _is_mid_word_boundary(text, end):
        return end

    snapped_end = end
    while snapped_end > start and _is_word_char(text[snapped_end - 1]):
        snapped_end -= 1

    if snapped_end <= start:
        # Long unbroken tokens cannot always avoid a mid-word split.
        return end

    return snapped_end


def _snap_start_forward_to_word_boundary(text: str, start: int, end: int) -> int:
    if not _is_mid_word_boundary(text, start):
        return start

    snapped_start = start
    while snapped_start < end and _is_mid_word_boundary(text, snapped_start):
        snapped_start += 1
    return snapped_start


def _resolve_chunking_params(size: int | None, overlap: int | None) -> tuple[int, int]:
    settings = get_settings()
    resolved_size = settings.chunk_size_chars if size is None else size
    resolved_overlap = settings.chunk_overlap_chars if overlap is None else overlap
    return resolved_size, resolved_overlap


def chunk_text(text: str, size: int | None = None, overlap: int | None = None) -> list[str]:
    """Split text into deterministic character chunks with overlap."""

    size, overlap = _resolve_chunking_params(size=size, overlap=overlap)

    if size <= 0:
        raise ValueError("size must be greater than 0.")
    if overlap < 0:
        raise ValueError("overlap must be greater than or equal to 0.")
    if overlap >= size:
        raise ValueError("overlap must be smaller than size.")
    if not text:
        return []

    chunks: list[str] = []
    text_length = len(text)
    start = 0

    while start < text_length:
        hard_end = min(start + size, text_length)
        end = _snap_end_to_word_boundary(text, start, hard_end)

        if end < text_length and (end - start) <= overlap:
            end = hard_end

        if end <= start:
            end = hard_end

        chunk = text[start:end]

        if chunk.strip():
            chunks.append(chunk)

        if end >= text_length:
            break

        next_start = end - overlap
        next_start = _snap_start_forward_to_word_boundary(text, next_start, end)

        if next_start <= start:
            next_start = end

        start = next_start

    return chunks


def prepare_doc_embedding_text(chunk: str) -> str:
    """Prefix chunk text for document embeddings with Nomic format."""

    return f"{_DOC_EMBEDDING_PREFIX}{chunk}"


def prepare_query_embedding_text(q: str) -> str:
    """Prefix query text for query embeddings with Nomic format."""

    return f"{_QUERY_EMBEDDING_PREFIX}{q}"
