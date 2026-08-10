"""Async Ollama embedding client using the native `/api/embed` endpoint."""

from __future__ import annotations

import asyncio
import logging
import math
from dataclasses import dataclass
from time import perf_counter
from typing import Any
from urllib.parse import SplitResult, urlsplit, urlunsplit
from uuid import UUID

import httpx

from app.core.settings import get_settings
from app.utils.chunking import prepare_doc_embedding_text, prepare_query_embedding_text

logger = logging.getLogger(__name__)


class OllamaEmbeddingError(RuntimeError):
    """Raised when Ollama returns a non-retryable embedding error."""


class OllamaTransientEmbeddingError(OllamaEmbeddingError):
    """Raised when Ollama embedding errors are transient and should be retried."""


class OllamaMalformedResponseError(OllamaEmbeddingError):
    """Raised when Ollama returns a malformed embedding response."""


class EmbeddingCardinalityMismatchError(OllamaEmbeddingError):
    """Raised when Ollama returns a different number of embeddings than requested."""


class EmbeddingDimensionMismatchError(OllamaEmbeddingError):
    """Raised when Ollama returns an embedding of unexpected dimensionality."""


@dataclass(slots=True)
class _EmbeddingCallMetrics:
    input_count: int
    batch_size: int
    http_batch_count: int = 0
    retry_count: int = 0
    completed_count: int = 0


def _resolve_ollama_base_url(openai_base_url: str) -> str:
    """Convert an OpenAI-style Ollama base URL (`.../v1`) to native Ollama base URL."""

    parsed = urlsplit(openai_base_url.strip())
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(
            "OLLAMA_OPENAI_BASE_URL must be an absolute URL, e.g. "
            "http://localhost:11434/v1."
        )

    path = parsed.path.rstrip("/")
    if path.endswith("/v1"):
        path = path[: -len("/v1")]

    base_url = urlunsplit(
        SplitResult(
            scheme=parsed.scheme,
            netloc=parsed.netloc,
            path=path,
            query="",
            fragment="",
        )
    ).rstrip("/")
    return base_url


class OllamaEmbeddingClient:
    """Async client for local Ollama embeddings with retries and concurrency limits."""

    def __init__(
        self,
        *,
        settings: Any | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._embed_model: str = self._settings.ollama_embed_model
        self._embedding_dim = int(self._settings.embedding_dim)
        self._batch_size = int(getattr(self._settings, "ollama_embed_batch_size", 32))
        if not 1 <= self._batch_size <= 128:
            raise ValueError("OLLAMA_EMBED_BATCH_SIZE must be between 1 and 128 inclusive.")

        self._embed_endpoint = (
            f"{_resolve_ollama_base_url(self._settings.ollama_openai_base_url)}/api/embed"
        )

        connect_timeout = float(getattr(self._settings, "ollama_embed_connect_timeout_s", 5.0))
        read_timeout = float(getattr(self._settings, "ollama_embed_read_timeout_s", 120.0))
        limits = httpx.Limits(
            max_connections=int(getattr(self._settings, "ollama_embed_max_connections", 20)),
            max_keepalive_connections=int(
                getattr(self._settings, "ollama_embed_max_keepalive_connections", 10)
            ),
        )
        timeout = httpx.Timeout(
            connect=connect_timeout,
            read=read_timeout,
            write=read_timeout,
            pool=connect_timeout,
        )

        concurrency = int(getattr(self._settings, "embed_concurrency", 4))
        if concurrency <= 0:
            raise ValueError("EMBED_CONCURRENCY must be greater than 0.")

        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(timeout=timeout, limits=limits)
        self._semaphore = asyncio.Semaphore(concurrency)

    async def aclose(self) -> None:
        """Close the underlying HTTP client if owned by this instance."""
        if self._owns_client:
            await self._client.aclose()

    async def embed_documents(
        self,
        texts: list[str],
        *,
        job_id: UUID | None = None,
        document_id: UUID | None = None,
    ) -> list[list[float]]:
        """Embed document chunks in sequential, ordered batches."""
        started_at = perf_counter()
        metrics = _EmbeddingCallMetrics(
            input_count=len(texts),
            batch_size=self._batch_size,
        )
        status = "failure"

        try:
            if not texts:
                status = "success"
                return []

            prompts = [prepare_doc_embedding_text(text) for text in texts]
            embeddings: list[list[float]] = []
            for start in range(0, len(prompts), self._batch_size):
                prompt_batch = prompts[start : start + self._batch_size]
                metrics.http_batch_count += 1
                batch_embeddings = await self._embed_batch_with_retries(
                    prompt_batch,
                    metrics=metrics,
                )
                embeddings.extend(batch_embeddings)
                metrics.completed_count += len(batch_embeddings)

            if len(embeddings) != len(texts):
                raise EmbeddingCardinalityMismatchError(
                    "Ollama embeddings response cardinality did not match the submitted input count."
                )

            status = "success"
            return embeddings
        finally:
            duration_s = perf_counter() - started_at
            embeddings_per_s = metrics.completed_count / duration_s if duration_s > 0 else 0.0
            logger.info(
                "Embedding summary job_id=%s document_id=%s input_count=%s batch_size=%s "
                "http_batch_count=%s retry_count=%s duration_s=%.6f "
                "embeddings_per_s=%.3f status=%s",
                job_id,
                document_id,
                metrics.input_count,
                metrics.batch_size,
                metrics.http_batch_count,
                metrics.retry_count,
                duration_s,
                embeddings_per_s,
                status,
            )
            if metrics.retry_count:
                logger.info(
                    "Embedding retry summary job_id=%s document_id=%s retry_count=%s "
                    "status=%s",
                    job_id,
                    document_id,
                    metrics.retry_count,
                    status,
                )

    async def embed_query(self, text: str) -> list[float]:
        """Embed one query with the Nomic `search_query:` prefix."""
        embeddings = await self._embed_batch_with_retries(
            [prepare_query_embedding_text(text)],
            metrics=None,
        )
        if len(embeddings) != 1:
            raise EmbeddingCardinalityMismatchError(
                "Ollama query embedding response must contain exactly one embedding."
            )
        return embeddings[0]

    async def _embed_batch_with_retries(
        self,
        prompts: list[str],
        *,
        metrics: _EmbeddingCallMetrics | None,
    ) -> list[list[float]]:
        attempts = int(getattr(self._settings, "ollama_embed_retry_attempts", 3))
        min_wait = float(getattr(self._settings, "ollama_embed_retry_min_wait_s", 0.2))
        max_wait = float(getattr(self._settings, "ollama_embed_retry_max_wait_s", 2.0))

        for attempt_number in range(1, attempts + 1):
            try:
                async with self._semaphore:
                    return await self._request_embedding_batch(prompts)
            except OllamaTransientEmbeddingError:
                if attempt_number >= attempts:
                    raise
                if metrics is not None:
                    metrics.retry_count += 1
                wait_s = min(max_wait, min_wait * (2 ** (attempt_number - 1)))
                await asyncio.sleep(wait_s)

        raise RuntimeError("Embedding retry loop exited without returning a result.")

    async def _request_embedding_batch(self, prompts: list[str]) -> list[list[float]]:
        payload = {
            "model": self._embed_model,
            "input": prompts,
            "truncate": False,
        }
        try:
            response = await self._client.post(self._embed_endpoint, json=payload)
        except httpx.TimeoutException:
            raise OllamaTransientEmbeddingError(
                "Ollama embedding request timed out."
            ) from None
        except httpx.ConnectError:
            raise OllamaTransientEmbeddingError(
                "Ollama embedding connection failed."
            ) from None

        if response.status_code == 429 or 500 <= response.status_code <= 599:
            raise OllamaTransientEmbeddingError(
                f"Ollama embedding request returned transient status {response.status_code}."
            )
        if not 200 <= response.status_code <= 299:
            raise OllamaEmbeddingError(
                f"Ollama embedding request failed with status {response.status_code}."
            )

        try:
            body = response.json()
        except ValueError:
            raise OllamaMalformedResponseError(
                "Ollama embedding response is not valid JSON."
            ) from None

        if not isinstance(body, dict):
            raise OllamaMalformedResponseError(
                "Ollama embedding response must be a JSON object."
            )

        embeddings = body.get("embeddings")
        if not isinstance(embeddings, list):
            raise OllamaMalformedResponseError(
                "Ollama embedding response must contain an embeddings list."
            )
        if len(embeddings) != len(prompts):
            raise EmbeddingCardinalityMismatchError(
                "Ollama embedding response cardinality did not match the submitted input count."
            )

        parsed_embeddings: list[list[float]] = []
        for embedding in embeddings:
            if not isinstance(embedding, list):
                raise OllamaMalformedResponseError(
                    "Ollama embedding response contained a malformed embedding."
                )
            if len(embedding) != self._embedding_dim:
                raise EmbeddingDimensionMismatchError(
                    f"Embedding dimension mismatch: expected {self._embedding_dim}, "
                    f"got {len(embedding)}."
                )

            parsed_embedding: list[float] = []
            for value in embedding:
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise OllamaMalformedResponseError(
                        "Ollama embedding response contained a non-numeric value."
                    )
                parsed_value = float(value)
                if not math.isfinite(parsed_value):
                    raise OllamaMalformedResponseError(
                        "Ollama embedding response contained a non-finite value."
                    )
                parsed_embedding.append(parsed_value)
            parsed_embeddings.append(parsed_embedding)

        return parsed_embeddings


_DEFAULT_EMBEDDINGS_CLIENT: OllamaEmbeddingClient | None = None


def get_embeddings_client() -> OllamaEmbeddingClient:
    """Return the process-wide embeddings client and concurrency limiter."""
    global _DEFAULT_EMBEDDINGS_CLIENT
    if _DEFAULT_EMBEDDINGS_CLIENT is None:
        _DEFAULT_EMBEDDINGS_CLIENT = OllamaEmbeddingClient()
    return _DEFAULT_EMBEDDINGS_CLIENT


async def close_embeddings_client() -> None:
    """Close and reset the process-wide embeddings client and concurrency state."""
    global _DEFAULT_EMBEDDINGS_CLIENT
    if _DEFAULT_EMBEDDINGS_CLIENT is None:
        return

    client = _DEFAULT_EMBEDDINGS_CLIENT
    _DEFAULT_EMBEDDINGS_CLIENT = None
    await client.aclose()


async def embed_documents(
    texts: list[str],
    *,
    job_id: UUID | None = None,
    document_id: UUID | None = None,
) -> list[list[float]]:
    """Embed document chunks using the process-wide Ollama client."""
    return await get_embeddings_client().embed_documents(
        texts,
        job_id=job_id,
        document_id=document_id,
    )


async def embed_query(text: str) -> list[float]:
    """Embed one query using the process-wide Ollama client."""
    return await get_embeddings_client().embed_query(text)
