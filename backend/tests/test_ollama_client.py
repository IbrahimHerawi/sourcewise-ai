from __future__ import annotations

import asyncio
import json
import logging
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest

import app.services.embeddings as embeddings_service
from app.services.embeddings import (
    EmbeddingCardinalityMismatchError,
    EmbeddingDimensionMismatchError,
    OllamaEmbeddingClient,
    OllamaEmbeddingError,
    OllamaMalformedResponseError,
)


def _settings(**overrides: Any) -> SimpleNamespace:
    base = {
        "ollama_embed_model": "nomic-embed-text",
        "embedding_dim": 3,
        "ollama_openai_base_url": "http://localhost:11434/v1",
        "embed_concurrency": 2,
        "ollama_embed_batch_size": 32,
        "ollama_embed_connect_timeout_s": 0.1,
        "ollama_embed_read_timeout_s": 1.0,
        "ollama_embed_max_connections": 20,
        "ollama_embed_max_keepalive_connections": 10,
        "ollama_embed_retry_attempts": 3,
        "ollama_embed_retry_min_wait_s": 0.001,
        "ollama_embed_retry_max_wait_s": 0.01,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _vector(index: int) -> list[float]:
    return [float(index), float(index) + 0.1, float(index) + 0.2]


def _response_for_request(request: httpx.Request) -> httpx.Response:
    payload = json.loads(request.content.decode("utf-8"))
    return httpx.Response(
        200,
        json={"embeddings": [_vector(index) for index, _ in enumerate(payload["input"])]},
    )


@pytest.mark.asyncio
async def test_embed_documents_uses_api_embed_prefixes_and_no_truncation() -> None:
    request_payloads: list[dict[str, Any]] = []
    request_paths: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        request_paths.append(request.url.path)
        payload = json.loads(request.content.decode("utf-8"))
        request_payloads.append(payload)
        return httpx.Response(200, json={"embeddings": [_vector(0), _vector(1)]})

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = OllamaEmbeddingClient(settings=_settings(), http_client=http_client)

    vectors = await client.embed_documents(["alpha", "beta"])

    assert vectors == [_vector(0), _vector(1)]
    assert request_paths == ["/api/embed"]
    assert request_payloads == [
        {
            "model": "nomic-embed-text",
            "input": ["search_document: alpha", "search_document: beta"],
            "truncate": False,
        }
    ]
    await http_client.aclose()


@pytest.mark.asyncio
async def test_embed_documents_empty_input_makes_zero_requests() -> None:
    request_count = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(500)

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = OllamaEmbeddingClient(settings=_settings(), http_client=http_client)

    assert await client.embed_documents([]) == []
    assert request_count == 0
    await http_client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("input_count", "expected_batch_sizes"),
    [
        (1, [1]),
        (32, [32]),
        (33, [32, 1]),
        (65, [32, 32, 1]),
    ],
)
async def test_embed_documents_uses_bounded_ordered_batches(
    input_count: int,
    expected_batch_sizes: list[int],
) -> None:
    submitted_inputs: list[list[str]] = []
    next_vector_index = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal next_vector_index
        payload = json.loads(request.content.decode("utf-8"))
        submitted_inputs.append(payload["input"])
        batch_vectors = [
            _vector(index)
            for index in range(next_vector_index, next_vector_index + len(payload["input"]))
        ]
        next_vector_index += len(batch_vectors)
        return httpx.Response(200, json={"embeddings": batch_vectors})

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = OllamaEmbeddingClient(settings=_settings(), http_client=http_client)
    texts = [f"chunk-{index}" for index in range(input_count)]

    vectors = await client.embed_documents(texts)

    assert [len(batch) for batch in submitted_inputs] == expected_batch_sizes
    assert [item for batch in submitted_inputs for item in batch] == [
        f"search_document: {text}" for text in texts
    ]
    assert vectors == [_vector(index) for index in range(input_count)]
    await http_client.aclose()


@pytest.mark.asyncio
async def test_embed_query_uses_one_prefixed_input_and_requires_one_vector() -> None:
    request_payloads: list[dict[str, Any]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        request_payloads.append(json.loads(request.content.decode("utf-8")))
        return httpx.Response(200, json={"embeddings": [[0, 1.0, 2]]})

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = OllamaEmbeddingClient(settings=_settings(), http_client=http_client)

    vector = await client.embed_query("what is this")

    assert vector == [0.0, 1.0, 2.0]
    assert request_payloads == [
        {
            "model": "nomic-embed-text",
            "input": ["search_query: what is this"],
            "truncate": False,
        }
    ]
    await http_client.aclose()


@pytest.mark.asyncio
async def test_embed_query_rejects_cardinality_mismatch_without_retry() -> None:
    attempts = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(200, json={"embeddings": [_vector(0), _vector(1)]})

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = OllamaEmbeddingClient(settings=_settings(), http_client=http_client)

    with pytest.raises(EmbeddingCardinalityMismatchError):
        await client.embed_query("wrong count")

    assert attempts == 1
    await http_client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, content=b"not-json"),
        httpx.Response(200, json=[]),
        httpx.Response(200, json={}),
        httpx.Response(200, json={"embeddings": {}}),
        httpx.Response(200, json={"embeddings": ["not-a-vector"]}),
        httpx.Response(200, json={"embeddings": [[True, 0.2, 0.3]]}),
        httpx.Response(200, json={"embeddings": [["0.1", 0.2, 0.3]]}),
        httpx.Response(200, content=b'{"embeddings":[[NaN,0.2,0.3]]}'),
        httpx.Response(200, content=b'{"embeddings":[[Infinity,0.2,0.3]]}'),
        httpx.Response(200, content=b'{"embeddings":[[-Infinity,0.2,0.3]]}'),
    ],
)
async def test_malformed_responses_fail_complete_batch_without_retry(
    response: httpx.Response,
) -> None:
    attempts = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return response

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = OllamaEmbeddingClient(settings=_settings(), http_client=http_client)

    with pytest.raises(OllamaMalformedResponseError):
        await client.embed_documents(["alpha"])

    assert attempts == 1
    await http_client.aclose()


@pytest.mark.asyncio
async def test_dimension_mismatch_fails_complete_batch_without_retry() -> None:
    attempts = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(200, json={"embeddings": [_vector(0), [0.1, 0.2]]})

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = OllamaEmbeddingClient(settings=_settings(), http_client=http_client)

    with pytest.raises(EmbeddingDimensionMismatchError, match="expected 3, got 2"):
        await client.embed_documents(["alpha", "beta"])

    assert attempts == 1
    await http_client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [400, 401, 404])
async def test_non_transient_http_errors_are_not_retried(status_code: int) -> None:
    attempts = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(status_code, text="raw response body must not appear")

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = OllamaEmbeddingClient(settings=_settings(), http_client=http_client)

    with pytest.raises(OllamaEmbeddingError) as exc_info:
        await client.embed_query("do not retry")

    assert attempts == 1
    assert "raw response body" not in str(exc_info.value)
    await http_client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [429, 500, 503])
async def test_transient_http_statuses_are_retried(status_code: int) -> None:
    attempts = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(status_code, text="temporary raw body")
        return httpx.Response(200, json={"embeddings": [_vector(0)]})

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = OllamaEmbeddingClient(settings=_settings(), http_client=http_client)

    assert await client.embed_query("retry") == _vector(0)
    assert attempts == 2
    await http_client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "transient_error",
    [
        httpx.ConnectError("connection failed"),
        httpx.ReadTimeout("read timed out"),
    ],
)
async def test_connection_and_timeout_errors_are_retried(
    transient_error: httpx.RequestError,
) -> None:
    attempts = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise transient_error
        return httpx.Response(200, json={"embeddings": [_vector(0)]})

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = OllamaEmbeddingClient(settings=_settings(), http_client=http_client)

    assert await client.embed_query("retry transport") == _vector(0)
    assert attempts == 2
    await http_client.aclose()


@pytest.mark.asyncio
async def test_only_failed_later_batch_is_retried() -> None:
    submitted_batches: list[list[str]] = []
    last_batch_attempts = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal last_batch_attempts
        payload = json.loads(request.content.decode("utf-8"))
        prompts = payload["input"]
        submitted_batches.append(prompts)
        if len(prompts) == 1:
            last_batch_attempts += 1
            if last_batch_attempts == 1:
                return httpx.Response(500)
        return httpx.Response(200, json={"embeddings": [_vector(0) for _ in prompts]})

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = OllamaEmbeddingClient(settings=_settings(), http_client=http_client)

    vectors = await client.embed_documents([f"chunk-{index}" for index in range(65)])

    assert len(vectors) == 65
    assert [len(batch) for batch in submitted_batches] == [32, 32, 1, 1]
    assert submitted_batches[-1] == submitted_batches[-2]
    await http_client.aclose()


@pytest.mark.asyncio
async def test_batches_within_one_document_execute_sequentially() -> None:
    in_flight = 0
    peak_in_flight = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal in_flight, peak_in_flight
        in_flight += 1
        peak_in_flight = max(peak_in_flight, in_flight)
        await asyncio.sleep(0.01)
        in_flight -= 1
        return _response_for_request(request)

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = OllamaEmbeddingClient(
        settings=_settings(embed_concurrency=4),
        http_client=http_client,
    )

    vectors = await client.embed_documents([f"chunk-{index}" for index in range(65)])

    assert len(vectors) == 65
    assert peak_in_flight == 1
    await http_client.aclose()


@pytest.mark.asyncio
async def test_semaphore_is_shared_across_separate_document_and_query_calls() -> None:
    in_flight = 0
    peak_in_flight = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal in_flight, peak_in_flight
        in_flight += 1
        peak_in_flight = max(peak_in_flight, in_flight)
        await asyncio.sleep(0.02)
        in_flight -= 1
        return _response_for_request(request)

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = OllamaEmbeddingClient(
        settings=_settings(embed_concurrency=1),
        http_client=http_client,
    )

    document_vectors, query_vector = await asyncio.gather(
        client.embed_documents(["document"]),
        client.embed_query("query"),
    )

    assert len(document_vectors) == 1
    assert len(query_vector) == 3
    assert peak_in_flight == 1
    await http_client.aclose()


@pytest.mark.asyncio
async def test_document_summary_logs_are_safe_and_retry_log_is_conditional(
    caplog: pytest.LogCaptureFixture,
) -> None:
    attempts = 0
    job_id = uuid4()
    document_id = uuid4()

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(500, text="secret raw body")
        return httpx.Response(200, json={"embeddings": [_vector(0)]})

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = OllamaEmbeddingClient(settings=_settings(), http_client=http_client)
    embedding_logger = logging.getLogger(embeddings_service.__name__)
    previous_propagate = embedding_logger.propagate
    previous_disabled = embedding_logger.disabled

    # The application lifespan can replace root handlers. Attach the capture
    # handler directly so this unit test verifies the service log contract
    # rather than depending on prior application lifecycle tests.
    embedding_logger.propagate = False
    embedding_logger.disabled = False
    embedding_logger.addHandler(caplog.handler)
    try:
        with caplog.at_level(logging.INFO, logger=embeddings_service.__name__):
            await client.embed_documents(
                ["secret chunk text"],
                job_id=job_id,
                document_id=document_id,
            )
    finally:
        embedding_logger.removeHandler(caplog.handler)
        embedding_logger.propagate = previous_propagate
        embedding_logger.disabled = previous_disabled

    summaries = [record.message for record in caplog.records if "Embedding summary" in record.message]
    retries = [
        record.message for record in caplog.records if "Embedding retry summary" in record.message
    ]
    assert len(summaries) == 1
    assert len(retries) == 1
    assert str(job_id) in summaries[0]
    assert str(document_id) in summaries[0]
    assert "input_count=1" in summaries[0]
    assert "http_batch_count=1" in summaries[0]
    assert "retry_count=1" in summaries[0]
    assert "status=success" in summaries[0]
    assert "secret" not in caplog.text
    await http_client.aclose()


@pytest.mark.asyncio
async def test_shared_client_shutdown_closes_and_resets_client_and_semaphore(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_client = SimpleNamespace(aclose=AsyncMock(), semaphore=object())
    second_client = SimpleNamespace(aclose=AsyncMock(), semaphore=object())
    created_clients = iter([first_client, second_client])
    monkeypatch.setattr(embeddings_service, "_DEFAULT_EMBEDDINGS_CLIENT", None)
    monkeypatch.setattr(
        embeddings_service,
        "OllamaEmbeddingClient",
        lambda: next(created_clients),
    )

    assert embeddings_service.get_embeddings_client() is first_client
    assert embeddings_service.get_embeddings_client() is first_client

    await embeddings_service.close_embeddings_client()

    first_client.aclose.assert_awaited_once()
    assert embeddings_service._DEFAULT_EMBEDDINGS_CLIENT is None
    assert embeddings_service.get_embeddings_client() is second_client
    assert second_client.semaphore is not first_client.semaphore

    await embeddings_service.close_embeddings_client()


@pytest.mark.asyncio
async def test_public_document_and_query_helpers_use_same_shared_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id = uuid4()
    document_id = uuid4()
    shared_client = SimpleNamespace(
        embed_documents=AsyncMock(return_value=[_vector(0)]),
        embed_query=AsyncMock(return_value=_vector(1)),
    )
    monkeypatch.setattr(
        embeddings_service,
        "_DEFAULT_EMBEDDINGS_CLIENT",
        shared_client,
    )

    document_vectors = await embeddings_service.embed_documents(
        ["document"],
        job_id=job_id,
        document_id=document_id,
    )
    query_vector = await embeddings_service.embed_query("query")

    assert document_vectors == [_vector(0)]
    assert query_vector == _vector(1)
    shared_client.embed_documents.assert_awaited_once_with(
        ["document"],
        job_id=job_id,
        document_id=document_id,
    )
    shared_client.embed_query.assert_awaited_once_with("query")
