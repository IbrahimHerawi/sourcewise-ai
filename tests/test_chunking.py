from __future__ import annotations

from types import SimpleNamespace

import pytest

import app.utils.chunking as chunking
from app.core.settings import Settings
from app.utils.chunking import (
    CHUNK_OVERLAP_CHARS,
    CHUNK_SIZE_CHARS,
    chunk_text,
    prepare_doc_embedding_text,
    prepare_query_embedding_text,
)


def test_chunk_text_uses_expected_defaults() -> None:
    assert CHUNK_SIZE_CHARS == 1200
    assert CHUNK_OVERLAP_CHARS == 200


def test_settings_reject_overlap_gte_size() -> None:
    with pytest.raises(ValueError, match="CHUNK_OVERLAP_CHARS must be less than CHUNK_SIZE_CHARS"):
        Settings(chunk_size_chars=10, chunk_overlap_chars=10)


def test_chunk_text_validates_size_and_overlap() -> None:
    with pytest.raises(ValueError, match="size must be greater than 0"):
        chunk_text("abc", size=0, overlap=0)

    with pytest.raises(ValueError, match="overlap must be greater than or equal to 0"):
        chunk_text("abc", size=3, overlap=-1)

    with pytest.raises(ValueError, match="overlap must be smaller than size"):
        chunk_text("abc", size=3, overlap=3)


def test_chunk_text_reads_defaults_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        chunking,
        "get_settings",
        lambda: SimpleNamespace(chunk_size_chars=10, chunk_overlap_chars=3),
    )

    assert chunking.chunk_text("one two three four five") == ["one two ", " three ", " four five"]


def test_chunk_text_skips_whitespace_only_chunks() -> None:
    assert chunk_text(" \n\t  ", size=4, overlap=1) == []


def test_chunk_text_avoids_mid_word_splits_when_possible() -> None:
    text = "alpha bravo charlie delta echo foxtrot golf hotel india juliet"

    chunks = chunk_text(text, size=18, overlap=5)

    assert chunks == [
        "alpha bravo ",
        " charlie delta ",
        " echo foxtrot golf",
        " golf hotel india ",
        " juliet",
    ]


def test_chunk_text_uses_hard_split_for_long_unbroken_tokens() -> None:
    text = "x" * 25

    chunks = chunk_text(text, size=10, overlap=3)

    assert chunks == ["x" * 10, "x" * 10, "x" * 5]


def test_prepare_doc_embedding_text_adds_nomic_prefix() -> None:
    assert prepare_doc_embedding_text("hello") == "search_document: hello"


def test_prepare_query_embedding_text_adds_nomic_prefix() -> None:
    assert prepare_query_embedding_text("what is this") == "search_query: what is this"
