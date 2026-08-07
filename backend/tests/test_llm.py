from __future__ import annotations

import json
import logging
from dataclasses import FrozenInstanceError
from types import SimpleNamespace

import httpx
import pytest
from openai import (
    APIConnectionError,
    APIResponseValidationError,
    APIStatusError,
    APITimeoutError,
    RateLimitError,
)

from app.core.settings import Settings
from app.services import llm


def _payload(
    *,
    answerable: bool = True,
    claims: list[dict[str, object]] | None = None,
) -> str:
    return json.dumps(
        {
            "answerable": answerable,
            "claims": claims
            if claims is not None
            else [{"text": "Answer from model", "citation_rank": 1}],
        }
    )


def _response(
    content: object,
    *,
    model: object = "response-model",
) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        model=model,
    )


class _FakeCompletions:
    def __init__(
        self,
        recorder: dict[str, object],
        owner: type[_FakeAsyncOpenAI],
    ) -> None:
        self._recorder = recorder
        self._owner = owner

    async def create(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        response_format: dict[str, object],
        temperature: int,
    ) -> SimpleNamespace:
        self._recorder["model"] = model
        self._recorder["messages"] = messages
        self._recorder["response_format"] = response_format
        self._recorder["temperature"] = temperature
        self._recorder["calls"] = int(self._recorder.get("calls", 0)) + 1

        if self._owner.side_effects:
            result = self._owner.side_effects.pop(0)
            if isinstance(result, BaseException):
                raise result
            return result

        return _response(
            self._owner.response_text,
            model=self._owner.response_model,
        )


class _FakeAsyncOpenAI:
    response_text: object = _payload()
    response_model: object = "response-model"
    side_effects: list[object] = []
    instances: list[_FakeAsyncOpenAI] = []

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout: httpx.Timeout,
        max_retries: int,
    ) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.recorder: dict[str, object] = {}
        self.chat = SimpleNamespace(
            completions=_FakeCompletions(self.recorder, self.__class__)
        )
        self.closed = False
        self.__class__.instances.append(self)

    async def __aenter__(self) -> _FakeAsyncOpenAI:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self.closed = True


@pytest.fixture(autouse=True)
def reset_fake_client() -> None:
    _FakeAsyncOpenAI.instances.clear()
    _FakeAsyncOpenAI.response_text = _payload()
    _FakeAsyncOpenAI.response_model = "response-model"
    _FakeAsyncOpenAI.side_effects = []


def _ollama_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "ai_provider": "ollama",
        "ollama_openai_base_url": "http://ollama:11434/v1",
        "ollama_chat_model": "llama3.2:1b",
        "ollama_embed_model": "nomic-embed-text",
        "llm_retry_min_wait_s": 0.001,
        "llm_retry_max_wait_s": 0.001,
    }
    values.update(overrides)
    return Settings(**values, _env_file=None)


def _request(url: str = "https://provider.example/v1/chat/completions") -> httpx.Request:
    return httpx.Request("POST", url)


def _status_error(
    status_code: int,
    *,
    message: str = "Provider status error.",
    body: object | None = None,
    request: httpx.Request | None = None,
) -> APIStatusError:
    response = httpx.Response(status_code, request=request or _request())
    return APIStatusError(message, response=response, body=body)


def _rate_limit_error() -> RateLimitError:
    response = httpx.Response(429, request=_request())
    return RateLimitError("Provider rate limit.", response=response, body=None)


def _successful_response() -> SimpleNamespace:
    return _response(
        _payload(claims=[{"text": "Recovered answer", "citation_rank": 1}])
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("settings", "expected_base_url", "expected_api_key", "expected_model"),
    [
        (
            Settings(
                ai_provider="openai",
                openai_api_key="sk-test",
                openai_base_url="https://api.openai.com/v1",
                openai_chat_model="gpt-4.1-mini",
                _env_file=None,
            ),
            "https://api.openai.com/v1",
            "sk-test",
            "gpt-4.1-mini",
        ),
        (
            _ollama_settings(),
            "http://ollama:11434/v1",
            "ollama",
            "llama3.2:1b",
        ),
    ],
)
async def test_generate_answer_switches_provider_by_client_config_only(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
    expected_base_url: str,
    expected_api_key: str,
    expected_model: str,
) -> None:
    _FakeAsyncOpenAI.response_text = _payload(
        claims=[{"text": "Context-bound answer", "citation_rank": 1}]
    )
    monkeypatch.setattr(llm, "AsyncOpenAI", _FakeAsyncOpenAI)

    answer = await llm.generate_answer(
        "alpha facts",
        "What does alpha say?",
        1,
        settings=settings,
    )

    assert answer == llm.GeneratedAnswer(
        answer_text="Context-bound answer. [1]",
        model_used="response-model",
        citation_ranks=(1,),
    )

    client = _FakeAsyncOpenAI.instances[-1]
    assert client.base_url == expected_base_url
    assert client.api_key == expected_api_key
    assert client.closed is True
    assert client.recorder["calls"] == 1
    assert client.recorder["model"] == expected_model
    assert client.recorder["temperature"] == 0
    assert client.recorder["messages"] == [
        {"role": "system", "content": llm.SYSTEM_PROMPT},
        {
            "role": "user",
            "content": "CONTEXT:\nalpha facts\n\nQUESTION:\nWhat does alpha say?",
        },
    ]
    response_format = client.recorder["response_format"]
    assert isinstance(response_format, dict)
    schema = response_format["json_schema"]["schema"]  # type: ignore[index]
    rank_schema = schema["properties"]["claims"]["items"]["properties"][  # type: ignore[index]
        "citation_rank"
    ]
    assert rank_schema == {"type": "integer", "minimum": 1, "maximum": 1}


def test_system_prompt_contains_the_complete_grounding_contract() -> None:
    assert "only from numbered document context entries" in llm.SYSTEM_PROMPT
    assert "exactly one fact directly stated" in llm.SYSTEM_PROMPT
    assert "citation_rank" in llm.SYSTEM_PROMPT
    assert "Do not use general knowledge" in llm.SYSTEM_PROMPT
    assert "answerable to false" in llm.SYSTEM_PROMPT


def test_generated_answer_is_immutable() -> None:
    answer = llm.GeneratedAnswer(
        answer_text="Supported [1].",
        model_used="test-model",
        citation_ranks=(1,),
    )

    with pytest.raises(FrozenInstanceError):
        answer.answer_text = "Changed."  # type: ignore[misc]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("claims", "expected_text", "expected_ranks"),
    [
        (
            [{"text": "One supported fact", "citation_rank": 1}],
            "One supported fact. [1]",
            (1,),
        ),
        (
            [
                {"text": "First fact", "citation_rank": 1},
                {"text": "Second fact.", "citation_rank": 2},
            ],
            "- First fact. [1]\n- Second fact. [2]",
            (1, 2),
        ),
        (
            [
                {"text": "Repeated support", "citation_rank": 2},
                {"text": "Repeated support", "citation_rank": 2},
                {"text": "Another claim", "citation_rank": 2},
            ],
            "- Repeated support. [2]\n- Another claim. [2]",
            (2,),
        ),
        (
            [
                {"text": "Second entry first", "citation_rank": 2},
                {"text": "Then first", "citation_rank": 1},
            ],
            "- Second entry first. [2]\n- Then first. [1]",
            (2, 1),
        ),
    ],
)
async def test_structured_claims_are_rendered_and_citations_deduplicated(
    monkeypatch: pytest.MonkeyPatch,
    claims: list[dict[str, object]],
    expected_text: str,
    expected_ranks: tuple[int, ...],
) -> None:
    monkeypatch.setattr(llm, "AsyncOpenAI", _FakeAsyncOpenAI)
    _FakeAsyncOpenAI.response_text = _payload(claims=claims)

    answer = await llm.generate_answer(
        "numbered context",
        "question",
        2,
        settings=_ollama_settings(),
    )

    assert answer == llm.GeneratedAnswer(
        answer_text=expected_text,
        model_used="response-model",
        citation_ranks=expected_ranks,
    )
    assert _FakeAsyncOpenAI.instances[-1].recorder["calls"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response_text",
    [
        _payload(answerable=False, claims=[]),
        _payload(answerable=False, claims=[{"text": "Contradiction", "citation_rank": 1}]),
        _payload(answerable=True, claims=[]),
        _payload(claims=[{"text": "Out of range", "citation_rank": 3}]),
        _payload(claims=[{"text": "Model-added marker [1]", "citation_rank": 1}]),
        _payload(claims=[{"text": "   ", "citation_rank": 1}]),
    ],
)
async def test_unsupported_or_invalid_grounding_becomes_fallback(
    monkeypatch: pytest.MonkeyPatch,
    response_text: str,
) -> None:
    monkeypatch.setattr(llm, "AsyncOpenAI", _FakeAsyncOpenAI)
    _FakeAsyncOpenAI.response_text = response_text

    answer = await llm.generate_answer(
        "two numbered entries",
        "question",
        2,
        settings=_ollama_settings(llm_retry_attempts=3),
    )

    assert answer == llm.GeneratedAnswer(
        answer_text=llm.FALLBACK_ANSWER,
        model_used="response-model",
        citation_ranks=(),
    )
    assert _FakeAsyncOpenAI.instances[-1].recorder["calls"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("response_text", ["", "not json", "{}", "[]"])
async def test_malformed_structured_output_is_invalid_without_retry(
    monkeypatch: pytest.MonkeyPatch,
    response_text: str,
) -> None:
    monkeypatch.setattr(llm, "AsyncOpenAI", _FakeAsyncOpenAI)
    _FakeAsyncOpenAI.response_text = response_text

    with pytest.raises(llm.LLMInvalidResponseError):
        await llm.generate_answer(
            "context",
            "question",
            1,
            settings=_ollama_settings(llm_retry_attempts=3),
        )

    assert _FakeAsyncOpenAI.instances[-1].recorder["calls"] == 1


@pytest.mark.asyncio
async def test_zero_context_returns_fallback_without_calling_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(llm, "AsyncOpenAI", _FakeAsyncOpenAI)

    answer = await llm.generate_answer(
        "",
        "question",
        0,
        settings=_ollama_settings(),
    )

    assert answer == llm.GeneratedAnswer(
        answer_text=llm.FALLBACK_ANSWER,
        model_used="llama3.2:1b",
        citation_ranks=(),
    )
    assert _FakeAsyncOpenAI.instances == []


def test_build_openai_client_configures_timeouts_and_disables_sdk_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(llm, "AsyncOpenAI", _FakeAsyncOpenAI)

    client = llm.build_openai_client(
        _ollama_settings(
            llm_connect_timeout_s=1.25,
            llm_read_timeout_s=9.5,
        )
    )

    assert isinstance(client, _FakeAsyncOpenAI)
    assert client.base_url == "http://ollama:11434/v1"
    assert client.api_key == "ollama"
    assert client.timeout.connect == 1.25
    assert client.timeout.read == 9.5
    assert client.timeout.write == 9.5
    assert client.timeout.pool == 1.25
    assert client.max_retries == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider_error", "expected_category", "expected_status"),
    [
        (
            APIConnectionError(message="Connection failed.", request=_request()),
            "connection",
            None,
        ),
        (APITimeoutError(_request()), "timeout", None),
        (_rate_limit_error(), "rate_limit", 429),
        (_status_error(429), "rate_limit", 429),
        (_status_error(503), "server_error", 503),
    ],
)
async def test_retryable_provider_failures_are_classified_and_retried(
    monkeypatch: pytest.MonkeyPatch,
    provider_error: Exception,
    expected_category: str,
    expected_status: int | None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(llm, "AsyncOpenAI", _FakeAsyncOpenAI)
    _FakeAsyncOpenAI.side_effects = [provider_error, _successful_response()]
    caplog.set_level(logging.WARNING, logger=llm.__name__)

    answer = await llm.generate_answer(
        "context",
        "question",
        1,
        settings=_ollama_settings(llm_retry_attempts=2),
    )

    assert answer == llm.GeneratedAnswer(
        answer_text="Recovered answer. [1]",
        model_used="response-model",
        citation_ranks=(1,),
    )
    client = _FakeAsyncOpenAI.instances[-1]
    assert client.recorder["calls"] == 2
    assert f"category={expected_category}" in caplog.text
    expected_log_status = expected_status if expected_status is not None else "none"
    assert f"status={expected_log_status}" in caplog.text


@pytest.mark.asyncio
async def test_retry_loop_stops_at_exact_configured_attempt_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(llm, "AsyncOpenAI", _FakeAsyncOpenAI)
    _FakeAsyncOpenAI.side_effects = [_status_error(500) for _ in range(3)]

    with pytest.raises(llm.LLMTransientError) as exc_info:
        await llm.generate_answer(
            "context",
            "question",
            1,
            settings=_ollama_settings(llm_retry_attempts=3),
        )

    assert exc_info.value.category == "server_error"
    assert exc_info.value.status_code == 500
    assert _FakeAsyncOpenAI.instances[-1].recorder["calls"] == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [400, 401, 403, 404, 422])
async def test_non_transient_http_4xx_is_rejected_without_retry(
    monkeypatch: pytest.MonkeyPatch,
    status_code: int,
) -> None:
    monkeypatch.setattr(llm, "AsyncOpenAI", _FakeAsyncOpenAI)
    _FakeAsyncOpenAI.side_effects = [_status_error(status_code)]

    with pytest.raises(llm.LLMRejectedError) as exc_info:
        await llm.generate_answer(
            "context",
            "question",
            1,
            settings=_ollama_settings(llm_retry_attempts=3),
        )

    assert exc_info.value.status_code == status_code
    assert _FakeAsyncOpenAI.instances[-1].recorder["calls"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("response_text", [None, 123])
async def test_non_text_successful_content_is_invalid_without_retry(
    monkeypatch: pytest.MonkeyPatch,
    response_text: object,
) -> None:
    monkeypatch.setattr(llm, "AsyncOpenAI", _FakeAsyncOpenAI)
    _FakeAsyncOpenAI.response_text = response_text

    with pytest.raises(llm.LLMInvalidResponseError):
        await llm.generate_answer(
            "context",
            "question",
            1,
            settings=_ollama_settings(llm_retry_attempts=3),
        )

    assert _FakeAsyncOpenAI.instances[-1].recorder["calls"] == 1


@pytest.mark.asyncio
async def test_sdk_response_validation_failure_is_invalid_without_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(llm, "AsyncOpenAI", _FakeAsyncOpenAI)
    response = httpx.Response(200, request=_request())
    _FakeAsyncOpenAI.side_effects = [
        APIResponseValidationError(
            response,
            {"raw": "unusable"},
            message="Malformed successful response.",
        )
    ]

    with pytest.raises(llm.LLMInvalidResponseError):
        await llm.generate_answer(
            "context",
            "question",
            1,
            settings=_ollama_settings(llm_retry_attempts=3),
        )

    assert _FakeAsyncOpenAI.instances[-1].recorder["calls"] == 1


@pytest.mark.asyncio
async def test_invalid_local_provider_configuration_is_not_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(llm, "AsyncOpenAI", _FakeAsyncOpenAI)
    settings = _ollama_settings()
    settings.ollama_chat_model = ""

    with pytest.raises(ValueError, match="OLLAMA_CHAT_MODEL"):
        await llm.generate_answer("context", "question", 1, settings=settings)

    assert _FakeAsyncOpenAI.instances == []


@pytest.mark.asyncio
async def test_errors_and_diagnostic_logs_exclude_request_and_secret_data(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(llm, "AsyncOpenAI", _FakeAsyncOpenAI)
    api_key = "sk-never-log-this"
    authorization = "Bearer never-log-authorization"
    prompt = "never-log-question"
    context = "never-log-context"
    raw_body = "never-log-raw-provider-body"
    secret_url_value = "never-log-url-secret"
    secret_url = f"https://user:{secret_url_value}@provider.example/v1?token={secret_url_value}"
    request = httpx.Request(
        "POST",
        secret_url,
        headers={"Authorization": authorization},
        content=f"{context} {prompt}",
    )
    provider_message = f"{api_key} {authorization} {prompt} {context} {raw_body} {secret_url}"
    _FakeAsyncOpenAI.side_effects = [
        _status_error(
            503,
            message=provider_message,
            body={"raw": raw_body},
            request=request,
        )
        for _ in range(2)
    ]
    caplog.set_level(logging.INFO, logger=llm.__name__)
    settings = Settings(
        ai_provider="openai",
        openai_api_key=api_key,
        openai_base_url=secret_url,
        openai_chat_model="gpt-safe-model",
        llm_retry_attempts=2,
        llm_retry_min_wait_s=0.001,
        llm_retry_max_wait_s=0.001,
        _env_file=None,
    )

    with pytest.raises(llm.LLMTransientError) as exc_info:
        await llm.generate_answer(context, prompt, 1, settings=settings)

    rendered = f"{caplog.text}\n{exc_info.value!s}\n{exc_info.value!r}"
    for sensitive_value in [
        api_key,
        authorization,
        prompt,
        context,
        raw_body,
        secret_url_value,
        secret_url,
    ]:
        assert sensitive_value not in rendered

    assert "provider=openai" in caplog.text
    assert "model=gpt-safe-model" in caplog.text
    assert "status=503" in caplog.text
    assert "category=server_error" in caplog.text
    assert "attempt=1" in caplog.text
    assert "attempt=2" in caplog.text
    assert "duration_s=" in caplog.text
