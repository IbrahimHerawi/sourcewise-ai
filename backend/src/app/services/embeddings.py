"""Async Ollama embedding client using the native `/api/embeddings` endpoint."""

from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import SplitResult, urlsplit, urlunsplit

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.settings import get_settings
from app.utils.chunking import prepare_doc_embedding_text, prepare_query_embedding_text


class OllamaEmbeddingError(RuntimeError):
    """Raised when Ollama returns a non-retryable embedding error."""


class OllamaTransientEmbeddingError(OllamaEmbeddingError):
    """Raised when Ollama embedding errors are transient and should be retried."""


class EmbeddingDimensionMismatchError(OllamaEmbeddingError):
    """Raised when Ollama returns an embedding of unexpected dimensionality."""


def _resolve_ollama_base_url(openai_base_url: str) -> str:
    """Convert an OpenAI-style Ollama base URL (`.../v1`) to native Ollama base URL."""

    parsed = urlsplit(openai_base_url.strip())
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("OLLAMA_OPENAI_BASE_URL must be an absolute URL, e.g. http://localhost:11434/v1.")

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
        self._embedding_dim: int = self._settings.embedding_dim
        self._embed_endpoint = f"{_resolve_ollama_base_url(self._settings.ollama_openai_base_url)}/api/embeddings"

        connect_timeout = float(getattr(self._settings, "ollama_embed_connect_timeout_s", 5.0))
        read_timeout = float(getattr(self._settings, "ollama_embed_read_timeout_s", 30.0))
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

        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(timeout=timeout, limits=limits)
        self._semaphore = asyncio.Semaphore(int(getattr(self._settings, "embed_concurrency", 4)))

    async def aclose(self) -> None:
        """Close the underlying HTTP client if owned by this instance."""
        if self._owns_client:
            await self._client.aclose()

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed document chunks with the Nomic `search_document:` prefix."""
        if not texts:
            return []

        prompts = [prepare_doc_embedding_text(text) for text in texts]
        tasks = [self._embed_one(prompt) for prompt in prompts]
        return await asyncio.gather(*tasks)

    async def embed_query(self, text: str) -> list[float]:
        """Embed a query string with the Nomic `search_query:` prefix."""
        return await self._embed_one(prepare_query_embedding_text(text))

    async def _embed_one(self, prompt: str) -> list[float]:
        attempts = int(getattr(self._settings, "ollama_embed_retry_attempts", 3))
        min_wait = float(getattr(self._settings, "ollama_embed_retry_min_wait_s", 0.2))
        max_wait = float(getattr(self._settings, "ollama_embed_retry_max_wait_s", 2.0))
        retrying = AsyncRetrying(
            stop=stop_after_attempt(attempts),
            wait=wait_exponential(multiplier=min_wait, min=min_wait, max=max_wait),
            retry=retry_if_exception_type((OllamaTransientEmbeddingError, httpx.TimeoutException)),
            reraise=True,
        )
        async for attempt in retrying:
            with attempt:
                async with self._semaphore:
                    embedding = await self._request_embedding(prompt)
                    self._validate_embedding_length(embedding)
                    return embedding

        raise RuntimeError("Embedding retry loop exited without returning a result.")

    async def _request_embedding(self, prompt: str) -> list[float]:
        # Ollama native embeddings request shape:
        # POST /api/embeddings
        # {"model": "<model-name>", "prompt": "<single string>"}
        payload = {"model": self._embed_model, "prompt": prompt}
        try:
            response = await self._client.post(self._embed_endpoint, json=payload)
        except httpx.TimeoutException as exc:
            raise OllamaTransientEmbeddingError("Timed out calling Ollama embeddings endpoint.") from exc

        if response.status_code == 429 or 500 <= response.status_code <= 599:
            raise OllamaTransientEmbeddingError(
                f"Ollama embeddings request returned transient status {response.status_code}."
            )

        if response.is_error:
            raise OllamaEmbeddingError(
                f"Ollama embeddings request failed with status {response.status_code}: {response.text}"
            )

        try:
            body = response.json()
        except ValueError as exc:
            raise OllamaEmbeddingError("Ollama embeddings response is not valid JSON.") from exc

        # Ollama native response shape:
        # {"embedding": [float, ...], ...}
        embedding = body.get("embedding") if isinstance(body, dict) else None
        if not isinstance(embedding, list):
            raise OllamaEmbeddingError("Ollama embeddings response missing `embedding` list.")

        parsed: list[float] = []
        for value in embedding:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise OllamaEmbeddingError(
                    "Ollama embeddings response contained a non-numeric embedding value."
                )
            parsed.append(float(value))
        return parsed

    def _validate_embedding_length(self, embedding: list[float]) -> None:
        if len(embedding) != self._embedding_dim:
            raise EmbeddingDimensionMismatchError(
                f"Embedding dimension mismatch for model `{self._embed_model}`: "
                f"expected {self._embedding_dim}, got {len(embedding)}."
            )


_DEFAULT_EMBEDDINGS_CLIENT: OllamaEmbeddingClient | None = None


def get_embeddings_client() -> OllamaEmbeddingClient:
    """Return a process-wide embeddings client instance."""
    global _DEFAULT_EMBEDDINGS_CLIENT
    if _DEFAULT_EMBEDDINGS_CLIENT is None:
        _DEFAULT_EMBEDDINGS_CLIENT = OllamaEmbeddingClient()
    return _DEFAULT_EMBEDDINGS_CLIENT


async def close_embeddings_client() -> None:
    """Close and clear the process-wide embeddings client."""
    global _DEFAULT_EMBEDDINGS_CLIENT
    if _DEFAULT_EMBEDDINGS_CLIENT is None:
        return

    await _DEFAULT_EMBEDDINGS_CLIENT.aclose()
    _DEFAULT_EMBEDDINGS_CLIENT = None


async def embed_documents(texts: list[str]) -> list[list[float]]:
    """Embed many documents using local Ollama and the configured embed model."""
    return await get_embeddings_client().embed_documents(texts)


async def embed_query(text: str) -> list[float]:
    """Embed a single query using local Ollama and the configured embed model."""
    return await get_embeddings_client().embed_query(text)
