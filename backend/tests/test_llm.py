from __future__ import annotations

import logging
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


class _FakeResponses:
    def __init__(
        self,
        recorder: dict[str, object],
        owner: type[_FakeAsyncOpenAI],
    ) -> None:
        self._recorder = recorder
        self._owner = owner

    async def create(self, *, model: str, instructions: str, input: str) -> SimpleNamespace:
        self._recorder["model"] = model
        self._recorder["instructions"] = instructions
        self._recorder["input"] = input
        self._recorder["calls"] = int(self._recorder.get("calls", 0)) + 1

        if self._owner.side_effects:
            result = self._owner.side_effects.pop(0)
            if isinstance(result, BaseException):
                raise result
            return result

        return SimpleNamespace(
            output_text=self._owner.response_text,
            model=self._owner.response_model,
        )


class _FakeAsyncOpenAI:
    response_text: object = "Answer from model."
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
        self.responses = _FakeResponses(self.recorder, self.__class__)
        self.closed = False
        self.__class__.instances.append(self)

    async def __aenter__(self) -> _FakeAsyncOpenAI:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self.closed = True


@pytest.fixture(autouse=True)
def reset_fake_client() -> None:
    _FakeAsyncOpenAI.instances.clear()
    _FakeAsyncOpenAI.response_text = "Answer from model."
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


def _request(url: str = "https://provider.example/v1/responses") -> httpx.Request:
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
    return SimpleNamespace(output_text="Recovered answer.", model="response-model")


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
    _FakeAsyncOpenAI.response_text = "Context-bound answer."
    monkeypatch.setattr(llm, "AsyncOpenAI", _FakeAsyncOpenAI)

    answer_text, model_used = await llm.generate_answer(
        "alpha facts",
        "What does alpha say?",
        settings=settings,
    )

    assert answer_text == "Context-bound answer."
    assert model_used == "response-model"

    client = _FakeAsyncOpenAI.instances[-1]
    assert client.base_url == expected_base_url
    assert client.api_key == expected_api_key
    assert client.closed is True
    assert client.recorder["calls"] == 1
    assert client.recorder["model"] == expected_model
    assert client.recorder["instructions"] == llm.SYSTEM_PROMPT
    assert client.recorder["input"] == "CONTEXT:\nalpha facts\n\nQUESTION:\nWhat does alpha say?"


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
        settings=_ollama_settings(llm_retry_attempts=2),
    )

    assert answer == ("Recovered answer.", "response-model")
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
            settings=_ollama_settings(llm_retry_attempts=3),
        )

    assert exc_info.value.status_code == status_code
    assert _FakeAsyncOpenAI.instances[-1].recorder["calls"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("response_text", [None, "", "   ", 123])
async def test_empty_or_malformed_successful_content_is_invalid_without_retry(
    monkeypatch: pytest.MonkeyPatch,
    response_text: object,
) -> None:
    monkeypatch.setattr(llm, "AsyncOpenAI", _FakeAsyncOpenAI)
    _FakeAsyncOpenAI.response_text = response_text

    with pytest.raises(llm.LLMInvalidResponseError):
        await llm.generate_answer(
            "context",
            "question",
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
        await llm.generate_answer("context", "question", settings=settings)

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
        await llm.generate_answer(context, prompt, settings=settings)

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
