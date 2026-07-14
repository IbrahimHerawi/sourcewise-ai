"""Unified answer generation via the OpenAI Python client."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from time import perf_counter

import httpx
from openai import (
    APIConnectionError,
    APIResponseValidationError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    RateLimitError,
)
from openai.types.responses import Response
from pydantic import SecretStr
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.settings import Settings, get_settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Answer using ONLY the provided context. "
    "If the context does not contain a supported answer then do not provide any extra "
    "information, reply exactly with: I don't know based on the uploaded documents."
)


class _LLMError(RuntimeError):
    """Base class for safely classified chat-provider failures."""

    def __init__(
        self,
        message: str,
        *,
        category: str,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.status_code = status_code


class LLMTransientError(_LLMError):
    """Raised when a transient chat-provider failure exhausts configured attempts."""

    def __init__(self, *, category: str, status_code: int | None = None) -> None:
        super().__init__(
            f"Chat provider request failed with a transient error (category={category}).",
            category=category,
            status_code=status_code,
        )


class LLMRejectedError(_LLMError):
    """Raised when the chat provider rejects a request without a retryable status."""

    def __init__(self, *, status_code: int) -> None:
        super().__init__(
            f"Chat provider rejected the request (status={status_code}).",
            category="provider_rejection",
            status_code=status_code,
        )


class LLMInvalidResponseError(_LLMError):
    """Raised when a successful chat response is malformed or unusable."""

    def __init__(self) -> None:
        super().__init__(
            "Chat provider returned a malformed or unusable successful response.",
            category="invalid_response",
        )


@dataclass(frozen=True, slots=True)
class _ProviderConfig:
    provider: str
    base_url: str
    api_key: SecretStr
    model: str


def _resolve_provider_config(settings: Settings) -> _ProviderConfig:
    if settings.ai_provider == "openai":
        api_key = settings.openai_api_key
        base_url = settings.openai_base_url.strip()
        model = settings.openai_chat_model.strip() if settings.openai_chat_model else ""
        if api_key is None:
            raise ValueError("OPENAI_API_KEY must be set when AI_PROVIDER=openai.")
        if not base_url:
            raise ValueError("OPENAI_BASE_URL must be set when AI_PROVIDER=openai.")
        if not model:
            raise ValueError("OPENAI_CHAT_MODEL must be set when AI_PROVIDER=openai.")
        return _ProviderConfig(
            provider="openai",
            base_url=base_url,
            api_key=api_key,
            model=model,
        )

    if settings.ai_provider == "ollama":
        base_url = settings.ollama_openai_base_url.strip()
        model = settings.ollama_chat_model.strip()
        if not base_url:
            raise ValueError("OLLAMA_OPENAI_BASE_URL must be set when AI_PROVIDER=ollama.")
        if not model:
            raise ValueError("OLLAMA_CHAT_MODEL must be set when AI_PROVIDER=ollama.")
        return _ProviderConfig(
            provider="ollama",
            base_url=base_url,
            api_key=SecretStr("ollama"),
            model=model,
        )

    raise ValueError("Unsupported AI provider configuration.")


def build_openai_client(settings: Settings | None = None) -> AsyncOpenAI:
    """Build an AsyncOpenAI client configured for the selected provider."""
    resolved_settings = settings or get_settings()
    config = _resolve_provider_config(resolved_settings)
    timeout = httpx.Timeout(
        connect=resolved_settings.llm_connect_timeout_s,
        read=resolved_settings.llm_read_timeout_s,
        write=resolved_settings.llm_read_timeout_s,
        pool=resolved_settings.llm_connect_timeout_s,
    )
    return AsyncOpenAI(
        base_url=config.base_url,
        api_key=config.api_key.get_secret_value(),
        timeout=timeout,
        max_retries=0,
    )


def _build_input(context_chunks_text: str, question: str) -> str:
    return f"CONTEXT:\n{context_chunks_text}\n\nQUESTION:\n{question}"


def _extract_answer(response: Response, *, configured_model: str) -> tuple[str, str]:
    output_text = getattr(response, "output_text", None)
    if not isinstance(output_text, str) or not output_text.strip():
        raise LLMInvalidResponseError()

    response_model = getattr(response, "model", None)
    if response_model is None:
        model_used = configured_model
    elif not isinstance(response_model, str) or not response_model.strip():
        raise LLMInvalidResponseError()
    else:
        model_used = response_model.strip()

    return output_text.strip(), model_used


async def _request_generation(
    client: AsyncOpenAI,
    *,
    model: str,
    prompt_input: str,
) -> Response:
    try:
        return await client.responses.create(
            model=model,
            instructions=SYSTEM_PROMPT,
            input=prompt_input,
        )
    except APITimeoutError:
        raise LLMTransientError(category="timeout") from None
    except APIConnectionError:
        raise LLMTransientError(category="connection") from None
    except RateLimitError:
        raise LLMTransientError(category="rate_limit", status_code=429) from None
    except APIStatusError as exc:
        if exc.status_code == 429:
            raise LLMTransientError(category="rate_limit", status_code=429) from None
        if 500 <= exc.status_code <= 599:
            raise LLMTransientError(
                category="server_error",
                status_code=exc.status_code,
            ) from None
        raise LLMRejectedError(status_code=exc.status_code) from None
    except APIResponseValidationError:
        raise LLMInvalidResponseError() from None


def _log_generation_attempt(
    *,
    config: _ProviderConfig,
    status: str | int,
    category: str,
    attempt_number: int,
    started_at: float,
    level: int,
) -> None:
    logger.log(
        level,
        "LLM generation provider=%s model=%s status=%s category=%s attempt=%s duration_s=%.6f",
        config.provider,
        config.model,
        status,
        category,
        attempt_number,
        perf_counter() - started_at,
    )


async def generate_answer(
    context_chunks_text: str,
    question: str,
    *,
    settings: Settings | None = None,
) -> tuple[str, str]:
    """Generate an answer from context using the configured provider."""
    resolved_settings = settings or get_settings()
    config = _resolve_provider_config(resolved_settings)
    prompt_input = _build_input(context_chunks_text=context_chunks_text, question=question)
    retrying = AsyncRetrying(
        retry=retry_if_exception_type(LLMTransientError),
        stop=stop_after_attempt(resolved_settings.llm_retry_attempts),
        wait=wait_exponential(
            multiplier=resolved_settings.llm_retry_min_wait_s,
            min=resolved_settings.llm_retry_min_wait_s,
            max=resolved_settings.llm_retry_max_wait_s,
        ),
        reraise=True,
    )

    async with build_openai_client(resolved_settings) as client:
        async for attempt in retrying:
            with attempt:
                attempt_number = attempt.retry_state.attempt_number
                started_at = perf_counter()
                try:
                    response = await _request_generation(
                        client,
                        model=config.model,
                        prompt_input=prompt_input,
                    )
                    answer = _extract_answer(response, configured_model=config.model)
                except _LLMError as exc:
                    status: str | int = exc.status_code or (
                        "success" if isinstance(exc, LLMInvalidResponseError) else "none"
                    )
                    _log_generation_attempt(
                        config=config,
                        status=status,
                        category=exc.category,
                        attempt_number=attempt_number,
                        started_at=started_at,
                        level=logging.WARNING,
                    )
                    raise

                _log_generation_attempt(
                    config=config,
                    status="success",
                    category="none",
                    attempt_number=attempt_number,
                    started_at=started_at,
                    level=logging.INFO,
                )
                return answer

    raise RuntimeError("LLM retry loop exited without returning a result.")


__all__ = [
    "LLMInvalidResponseError",
    "LLMRejectedError",
    "LLMTransientError",
    "build_openai_client",
    "generate_answer",
]
