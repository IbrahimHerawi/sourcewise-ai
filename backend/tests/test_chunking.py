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
    settings = Settings(_env_file=None)

    assert CHUNK_SIZE_CHARS == 2000
    assert CHUNK_OVERLAP_CHARS == 100
    assert settings.chunk_size_chars == CHUNK_SIZE_CHARS
    assert settings.chunk_overlap_chars == CHUNK_OVERLAP_CHARS


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


def test_chunk_text_is_deterministic_nonblank_and_never_exceeds_maximum() -> None:
    text = ("alpha beta gamma delta epsilon\n" * 300).strip()

    first = chunk_text(text)
    second = chunk_text(text)

    assert first == second
    assert first
    assert all(chunk.strip() for chunk in first)
    assert all(len(chunk) <= CHUNK_SIZE_CHARS for chunk in first)


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


def test_chunk_text_preserves_requested_overlap_when_boundaries_allow_it() -> None:
    text = "aaaa bbbb cccc dddd eeee ffff"

    chunks = chunk_text(text, size=20, overlap=5)

    assert chunks == ["aaaa bbbb cccc dddd ", "dddd eeee ffff"]
    assert chunks[0][-5:] == chunks[1][:5]


def test_reference_sized_text_produces_fewer_than_1100_chunks() -> None:
    target_character_count = 2_037_412
    text = ("reference text with meaningful whitespace. " * 60_000)[:target_character_count]

    chunks = chunk_text(text)

    assert len(text) == target_character_count
    assert len(chunks) < 1_100
    assert all(chunk.strip() for chunk in chunks)
    assert all(len(chunk) <= CHUNK_SIZE_CHARS for chunk in chunks)


def test_prepare_doc_embedding_text_adds_nomic_prefix() -> None:
    assert prepare_doc_embedding_text("hello") == "search_document: hello"


def test_prepare_query_embedding_text_adds_nomic_prefix() -> None:
    assert prepare_query_embedding_text("what is this") == "search_query: what is this"
