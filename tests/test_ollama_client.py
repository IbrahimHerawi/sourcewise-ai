from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from app.services.embeddings import EmbeddingDimensionMismatchError, OllamaEmbeddingClient


def _settings(**overrides: Any) -> SimpleNamespace:
    base = {
        "ollama_embed_model": "nomic-embed-text",
        "embedding_dim": 3,
        "ollama_openai_base_url": "http://localhost:11434/v1",
        "embed_concurrency": 2,
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


@pytest.mark.asyncio
async def test_embed_documents_uses_nomic_document_prefix_and_api_endpoint() -> None:
    request_payloads: list[dict[str, Any]] = []
    request_paths: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        request_paths.append(request.url.path)
        request_payloads.append(json.loads(request.content.decode("utf-8")))
        return httpx.Response(200, json={"embedding": [0.1, 0.2, 0.3]})

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = OllamaEmbeddingClient(settings=_settings(), http_client=http_client)

    vectors = await client.embed_documents(["alpha", "beta"])

    assert vectors == [[0.1, 0.2, 0.3], [0.1, 0.2, 0.3]]
    assert request_paths == ["/api/embeddings", "/api/embeddings"]
    assert request_payloads == [
        {"model": "nomic-embed-text", "prompt": "search_document: alpha"},
        {"model": "nomic-embed-text", "prompt": "search_document: beta"},
    ]
    await http_client.aclose()


@pytest.mark.asyncio
async def test_embed_query_uses_nomic_query_prefix() -> None:
    request_payloads: list[dict[str, Any]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        request_payloads.append(json.loads(request.content.decode("utf-8")))
        return httpx.Response(200, json={"embedding": [0.1, 0.2, 0.3]})

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = OllamaEmbeddingClient(settings=_settings(), http_client=http_client)

    vector = await client.embed_query("what is this")

    assert vector == [0.1, 0.2, 0.3]
    assert request_payloads == [
        {"model": "nomic-embed-text", "prompt": "search_query: what is this"}
    ]
    await http_client.aclose()


@pytest.mark.asyncio
async def test_embed_query_retries_on_transient_5xx() -> None:
    attempts = {"count": 0}

    async def handler(_: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            return httpx.Response(500, json={"error": "temporary failure"})
        return httpx.Response(200, json={"embedding": [0.1, 0.2, 0.3]})

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = OllamaEmbeddingClient(settings=_settings(), http_client=http_client)

    vector = await client.embed_query("retry me")

    assert vector == [0.1, 0.2, 0.3]
    assert attempts["count"] == 2
    await http_client.aclose()


@pytest.mark.asyncio
async def test_embed_query_retries_on_timeout() -> None:
    attempts = {"count": 0}

    async def handler(_: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise httpx.ReadTimeout("timed out")
        return httpx.Response(200, json={"embedding": [0.1, 0.2, 0.3]})

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = OllamaEmbeddingClient(settings=_settings(), http_client=http_client)

    vector = await client.embed_query("retry timeout")

    assert vector == [0.1, 0.2, 0.3]
    assert attempts["count"] == 2
    await http_client.aclose()


@pytest.mark.asyncio
async def test_embed_documents_respects_embed_concurrency_limit() -> None:
    in_flight = 0
    peak_in_flight = 0
    lock = asyncio.Lock()

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal in_flight, peak_in_flight
        async with lock:
            in_flight += 1
            peak_in_flight = max(peak_in_flight, in_flight)

        await asyncio.sleep(0.03)

        async with lock:
            in_flight -= 1
        return httpx.Response(200, json={"embedding": [0.1, 0.2, 0.3]})

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = OllamaEmbeddingClient(
        settings=_settings(embed_concurrency=2),
        http_client=http_client,
    )

    vectors = await client.embed_documents(["a", "b", "c", "d", "e"])

    assert len(vectors) == 5
    assert peak_in_flight == 2
    await http_client.aclose()


@pytest.mark.asyncio
async def test_embed_query_raises_clear_error_on_dimension_mismatch() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"embedding": [0.1, 0.2]})

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = OllamaEmbeddingClient(settings=_settings(embedding_dim=3), http_client=http_client)

    with pytest.raises(EmbeddingDimensionMismatchError, match="expected 3, got 2"):
        await client.embed_query("bad dimensions")

    await http_client.aclose()
