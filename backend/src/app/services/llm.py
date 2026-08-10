"""Unified, schema-grounded answer generation via the OpenAI Python client."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Final

import httpx
from openai import (
    APIConnectionError,
    APIResponseValidationError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    RateLimitError,
)
from pydantic import BaseModel, ConfigDict, SecretStr, ValidationError
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.settings import Settings, get_settings

logger = logging.getLogger(__name__)

FALLBACK_ANSWER: Final[str] = "I could not find the answer in the uploaded documents."
SYSTEM_PROMPT: Final[str] = (
    "You answer questions only from numbered document context entries.\n"
    "Return data matching the required JSON schema.\n"
    "Set answerable to true only when the context directly answers the question.\n"
    "When answerable is true, return one or more concise claims. Each claim must contain "
    "exactly one fact directly stated in its cited context entry. Use that entry's number "
    "as citation_rank.\n"
    "Do not combine a fact from one entry with the citation rank of another entry.\n"
    "Do not put citation markers in claim text; citation_rank is the citation.\n"
    "Do not use general knowledge, make inferences, or add recommendations.\n"
    "When the context does not directly answer the question, set answerable to false and "
    "return an empty claims array."
)
_CITATION_PATTERN: Final[re.Pattern[str]] = re.compile(r"\[([0-9]+)\]")


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
    """Raised when transient chat-provider failures exhaust configured attempts."""

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


@dataclass(frozen=True, slots=True)
class GeneratedAnswer:
    """Validated answer text and its grounding metadata."""

    answer_text: str
    model_used: str
    citation_ranks: tuple[int, ...]


class _GroundedClaimPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    citation_rank: int


class _GroundedAnswerPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answerable: bool
    claims: list[_GroundedClaimPayload]


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


def _build_response_format(*, available_context_entries: int) -> dict[str, object]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "grounded_document_answer",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "answerable": {"type": "boolean"},
                    "claims": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "text": {"type": "string", "minLength": 1},
                                "citation_rank": {
                                    "type": "integer",
                                    "minimum": 1,
                                    "maximum": max(1, available_context_entries),
                                },
                            },
                            "required": ["text", "citation_rank"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["answerable", "claims"],
                "additionalProperties": False,
            },
        },
    }


def _extract_answer(response: Any, *, configured_model: str) -> tuple[str, str]:
    choices = getattr(response, "choices", None)
    if not isinstance(choices, list) or len(choices) != 1:
        raise LLMInvalidResponseError()

    message = getattr(choices[0], "message", None)
    content = getattr(message, "content", None)
    if not isinstance(content, str):
        raise LLMInvalidResponseError()

    response_model = getattr(response, "model", None)
    if response_model is None:
        model_used = configured_model
    elif not isinstance(response_model, str) or not response_model.strip():
        raise LLMInvalidResponseError()
    else:
        model_used = response_model.strip()

    return content, model_used


def _fallback(*, model_used: str) -> GeneratedAnswer:
    return GeneratedAnswer(
        answer_text=FALLBACK_ANSWER,
        model_used=model_used,
        citation_ranks=(),
    )


def _punctuate_claim(text: str) -> str:
    return text if text.endswith((".", "!", "?")) else f"{text}."


def _validate_generated_answer(
    answer_text: str,
    *,
    model_used: str,
    available_context_entries: int,
) -> GeneratedAnswer:
    try:
        payload = _GroundedAnswerPayload.model_validate_json(answer_text)
    except (ValidationError, ValueError):
        raise LLMInvalidResponseError() from None

    if not payload.answerable:
        return _fallback(model_used=model_used)
    if not payload.claims:
        return _fallback(model_used=model_used)

    rendered_claims: list[tuple[str, int]] = []
    seen_claims: set[tuple[str, int]] = set()
    citation_ranks: list[int] = []
    seen_ranks: set[int] = set()

    for claim in payload.claims:
        text = claim.text.strip()
        rank = claim.citation_rank
        if (
            not text
            or _CITATION_PATTERN.search(text)
            or rank <= 0
            or rank > available_context_entries
        ):
            return _fallback(model_used=model_used)

        normalized_claim = (text, rank)
        if normalized_claim not in seen_claims:
            seen_claims.add(normalized_claim)
            rendered_claims.append(normalized_claim)
        if rank not in seen_ranks:
            seen_ranks.add(rank)
            citation_ranks.append(rank)

    if not rendered_claims:
        return _fallback(model_used=model_used)

    if len(rendered_claims) == 1:
        text, rank = rendered_claims[0]
        rendered_answer = f"{_punctuate_claim(text)} [{rank}]"
    else:
        rendered_answer = "\n".join(
            f"- {_punctuate_claim(text)} [{rank}]" for text, rank in rendered_claims
        )

    return GeneratedAnswer(
        answer_text=rendered_answer,
        model_used=model_used,
        citation_ranks=tuple(citation_ranks),
    )


async def _request_generation(
    client: AsyncOpenAI,
    *,
    model: str,
    prompt_input: str,
    available_context_entries: int,
) -> Any:
    try:
        return await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt_input},
            ],
            response_format=_build_response_format(
                available_context_entries=available_context_entries
            ),
            temperature=0,
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
    available_context_entries: int,
    *,
    settings: Settings | None = None,
) -> GeneratedAnswer:
    """Generate a schema-constrained, citation-grounded answer."""
    if available_context_entries < 0:
        raise ValueError("available_context_entries must not be negative.")

    resolved_settings = settings or get_settings()
    config = _resolve_provider_config(resolved_settings)
    if available_context_entries == 0:
        return _fallback(model_used=config.model)

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
                        available_context_entries=available_context_entries,
                    )
                    answer_text, model_used = _extract_answer(
                        response,
                        configured_model=config.model,
                    )
                    generated_answer = _validate_generated_answer(
                        answer_text,
                        model_used=model_used,
                        available_context_entries=available_context_entries,
                    )
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
                return generated_answer

    raise RuntimeError("LLM retry loop exited without returning a result.")


__all__ = [
    "FALLBACK_ANSWER",
    "GeneratedAnswer",
    "LLMInvalidResponseError",
    "LLMRejectedError",
    "LLMTransientError",
    "build_openai_client",
    "generate_answer",
]
