from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.api.schemas import (
    CitationResponse,
    PaginatedQuestionHistoryResponse,
    QuestionAnswerRequest,
    QuestionAnswerResponse,
    QuestionHistoryItemResponse,
)


def _citation_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "rank": 1,
        "document_id": uuid4(),
        "document_filename": "research.txt",
        "chunk_id": uuid4(),
        "chunk_index": 0,
        "excerpt": "Supporting evidence.",
        "distance": 0.125,
    }
    payload.update(overrides)
    return payload


def test_question_request_normalizes_text_and_applies_trimmed_limits() -> None:
    request = QuestionAnswerRequest(question=f"  {'q' * 4_000}\n")

    assert request.question == "q" * 4_000

    for invalid_question in ("", "  \t\n", "q" * 4_001):
        with pytest.raises(ValidationError):
            QuestionAnswerRequest(question=invalid_question)


def test_question_request_accepts_at_most_one_optional_collection() -> None:
    collection_id = uuid4()

    assert QuestionAnswerRequest(question="Unscoped question").collection_id is None
    assert (
        QuestionAnswerRequest(
            question="Collection question",
            collection_id=collection_id,
        ).collection_id
        == collection_id
    )


@pytest.mark.parametrize(
    "field",
    [
        "conversation_id",
        "thread_id",
        "messages",
        "history",
        "previous_question",
        "previous_answer",
        "question_text",
        "unknown",
    ],
)
def test_question_request_rejects_obsolete_chat_and_unknown_fields(field: str) -> None:
    with pytest.raises(ValidationError) as error:
        QuestionAnswerRequest.model_validate(
            {
                "question": "One independent question",
                field: [],
            }
        )

    assert any(item["type"] == "extra_forbidden" for item in error.value.errors())


def test_question_request_accepts_and_deduplicates_document_ids() -> None:
    first_document_id = uuid4()
    second_document_id = uuid4()

    request = QuestionAnswerRequest.model_validate(
        {
            "question": "One independent question",
            "document_ids": [str(first_document_id), str(second_document_id), str(first_document_id)],
        }
    )

    assert request.document_ids == [first_document_id, second_document_id]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("rank", 0),
        ("rank", -1),
        ("rank", True),
        ("rank", "1"),
        ("chunk_index", -1),
        ("chunk_index", False),
        ("chunk_index", "0"),
        ("distance", float("nan")),
        ("distance", float("inf")),
        ("distance", float("-inf")),
        ("distance", True),
        ("distance", "0.25"),
    ],
)
def test_citation_rejects_invalid_numeric_values(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        CitationResponse.model_validate(_citation_payload(**{field: value}))


def test_citation_validates_identifiers_and_filename() -> None:
    citation = CitationResponse.model_validate(_citation_payload())

    assert isinstance(citation.document_id, UUID)
    assert isinstance(citation.chunk_id, UUID)
    assert citation.document_filename == "research.txt"

    with pytest.raises(ValidationError):
        CitationResponse.model_validate(_citation_payload(document_id="not-a-uuid"))


@pytest.mark.parametrize(
    ("length", "expected_suffix", "expected_length"),
    [
        (499, "x", 499),
        (500, "x", 500),
        (501, "…", 501),
    ],
)
def test_citation_excerpt_has_exact_boundary_behavior(
    length: int,
    expected_suffix: str,
    expected_length: int,
) -> None:
    payload = _citation_payload()
    payload["chunk_content"] = f" \n{'x' * length}\t "
    payload["similarity_score"] = payload.pop("distance")
    payload.pop("excerpt")

    citation = CitationResponse.model_validate(payload)

    assert len(citation.excerpt) == expected_length
    assert citation.excerpt.endswith(expected_suffix)
    assert citation.excerpt == ("x" * length if length <= 500 else f"{'x' * 500}…")


@pytest.mark.parametrize(
    "schema",
    [QuestionAnswerResponse, QuestionHistoryItemResponse],
)
def test_question_responses_allow_nullable_provider_and_model(schema: type) -> None:
    payload: dict[str, object] = {
        "question_id": uuid4(),
        "collection_id": None,
        "answer": "Answer",
        "citations": [CitationResponse.model_validate(_citation_payload())],
        "created_at": datetime.now(UTC),
        "provider": None,
        "model": None,
    }
    if schema is QuestionHistoryItemResponse:
        payload["question"] = "Question"

    response = schema.model_validate(payload)

    assert response.collection_id is None
    assert response.provider is None
    assert response.model is None


@pytest.mark.parametrize("provider", ["anthropic", "", 1])
def test_question_responses_reject_unsupported_providers(provider: object) -> None:
    with pytest.raises(ValidationError):
        QuestionAnswerResponse(
            question_id=uuid4(),
            answer="Answer",
            citations=[],
            created_at=datetime.now(UTC),
            provider=provider,
        )


def test_orm_serialization_excludes_private_and_persisted_fields() -> None:
    collection_id = uuid4()
    citation_record = SimpleNamespace(
        rank=1,
        document_id=uuid4(),
        document_filename="snapshot.txt",
        chunk_id=uuid4(),
        chunk_index=4,
        chunk_content=f"  {'e' * 501}  ",
        similarity_score=0.25,
        question_id=uuid4(),
        embedding=[0.1, 0.2],
        prompt="private prompt",
        storage_path="/private/snapshot.txt",
        user_id=uuid4(),
    )
    question_record = SimpleNamespace(
        id=uuid4(),
        collection_id=collection_id,
        question_text="What does the snapshot say?",
        question_embedding=[0.3, 0.4],
        answer_text="It contains evidence.",
        context_chunks=[citation_record],
        created_at=datetime.now(UTC),
        ai_provider=None,
        model_used=None,
        user_id=uuid4(),
        prompt="private prompt",
        storage_path="/private/question.txt",
    )

    answer = QuestionAnswerResponse.model_validate(question_record).model_dump()
    history = QuestionHistoryItemResponse.model_validate(question_record).model_dump()

    assert set(answer) == {
        "question_id",
        "collection_id",
        "answer",
        "citations",
        "created_at",
        "provider",
        "model",
    }
    assert set(history) == {
        "question_id",
        "collection_id",
        "question",
        "answer",
        "citations",
        "created_at",
        "provider",
        "model",
    }
    assert set(answer["citations"][0]) == {
        "rank",
        "document_id",
        "document_filename",
        "chunk_id",
        "chunk_index",
        "excerpt",
        "distance",
    }
    assert answer["citations"][0]["excerpt"] == f"{'e' * 500}…"


def test_paginated_question_history_contains_only_pagination_contract() -> None:
    page = PaginatedQuestionHistoryResponse(items=[], limit=20, offset=0, total=0)

    assert page.model_dump() == {
        "items": [],
        "limit": 20,
        "offset": 0,
        "total": 0,
    }

    with pytest.raises(ValidationError):
        PaginatedQuestionHistoryResponse(
            items=[],
            limit=20,
            offset=0,
            total=0,
            user_id=uuid4(),
        )
