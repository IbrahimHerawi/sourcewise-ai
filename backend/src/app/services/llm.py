"""Unified, timeout-bounded answer generation via the OpenAI Python client."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI
from openai.types.responses import Response

from app.core.settings import Settings, get_settings

logger = logging.getLogger(__name__)

GROUNDED_NOT_FOUND_ANSWER = "I could not find this information in the selected documents."

SYSTEM_PROMPT = (
    "Answer using ONLY the provided context. "
    "Extract precise facts such as email addresses verbatim when they appear in the context. "
    "If the context does not contain a supported answer then do not provide any extra information, reply exactly with: "
    f"{GROUNDED_NOT_FOUND_ANSWER}"
)
EMPTY_ANSWER_FALLBACK = GROUNDED_NOT_FOUND_ANSWER


class AnswerProviderError(RuntimeError):
    """Base class for a safe answer-provider failure."""


class AnswerProviderUnavailableError(AnswerProviderError):
    """Raised when the configured provider cannot answer a request right now."""


@dataclass(frozen=True, slots=True)
class _ProviderConfig:
    base_url: str
    api_key: str
    model: str


def _resolve_provider_config(settings: Settings) -> _ProviderConfig:
    if settings.ai_provider == "openai":
        api_key = settings.openai_api_key
        if api_key is None:
            raise ValueError("OPENAI_API_KEY must be set when AI_PROVIDER=openai.")
        if not settings.openai_base_url.strip():
            raise ValueError("OPENAI_BASE_URL must be set when AI_PROVIDER=openai.")
        if not settings.openai_chat_model:
            raise ValueError("OPENAI_CHAT_MODEL must be set when AI_PROVIDER=openai.")
        return _ProviderConfig(
            base_url=settings.openai_base_url,
            api_key=api_key.get_secret_value(),
            model=settings.openai_chat_model,
        )

    if settings.ai_provider == "ollama":
        if not settings.ollama_openai_base_url.strip():
            raise ValueError("OLLAMA_OPENAI_BASE_URL must be set when AI_PROVIDER=ollama.")
        if not settings.ollama_chat_model:
            raise ValueError("OLLAMA_CHAT_MODEL must be set when AI_PROVIDER=ollama.")
        return _ProviderConfig(
            base_url=settings.ollama_openai_base_url,
            api_key="ollama",
            model=settings.ollama_chat_model,
        )

    raise ValueError(f"Unsupported AI provider: {settings.ai_provider}")


def build_openai_client(settings: Settings | None = None) -> AsyncOpenAI:
    """Build an AsyncOpenAI client configured for the selected provider."""
    resolved_settings = settings or get_settings()
    config = _resolve_provider_config(resolved_settings)
    return AsyncOpenAI(base_url=config.base_url, api_key=config.api_key)


def _build_input(context_chunks_text: str, question: str) -> str:
    return f"CONTEXT:\n{context_chunks_text}\n\nQUESTION:\n{question}"


def _extract_answer_text(response: Response) -> str:
    output_text = getattr(response, "output_text", None)
    if output_text is None:
        return EMPTY_ANSWER_FALLBACK

    stripped_content = output_text.strip()
    return stripped_content or EMPTY_ANSWER_FALLBACK


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

    try:
        async with build_openai_client(resolved_settings) as client:
            response = await asyncio.wait_for(
                client.responses.create(
                    model=config.model,
                    instructions=SYSTEM_PROMPT,
                    input=prompt_input,
                ),
                timeout=float(getattr(resolved_settings, "answer_provider_timeout_s", 60.0)),
            )
    except (TimeoutError, APITimeoutError, APIConnectionError) as exc:
        logger.warning("Answer provider request failed: %s", type(exc).__name__)
        raise AnswerProviderUnavailableError("The answer provider is temporarily unavailable.") from exc
    except APIStatusError as exc:
        logger.warning("Answer provider returned status=%s", exc.status_code)
        if exc.status_code >= 500 or exc.status_code == 429:
            raise AnswerProviderUnavailableError("The answer provider is temporarily unavailable.") from exc
        raise AnswerProviderError("The answer provider rejected this request.") from exc

    return _extract_answer_text(response), response.model or config.model


__all__ = [
    "AnswerProviderError",
    "AnswerProviderUnavailableError",
    "GROUNDED_NOT_FOUND_ANSWER",
    "build_openai_client",
    "generate_answer",
]
