from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.settings import Settings
from app.services import llm


class _FakeResponses:
    def __init__(self, recorder: dict[str, object], response_text: str | None) -> None:
        self._recorder = recorder
        self._response_text = response_text

    async def create(self, *, model: str, instructions: str, input: str) -> SimpleNamespace:
        self._recorder["model"] = model
        self._recorder["instructions"] = instructions
        self._recorder["input"] = input
        return SimpleNamespace(
            output_text=self._response_text,
            model="response-model",
        )


class _FakeAsyncOpenAI:
    response_text: str | None = "Answer from model."
    instances: list[_FakeAsyncOpenAI] = []

    def __init__(self, *, base_url: str, api_key: str) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.recorder: dict[str, object] = {}
        self.responses = _FakeResponses(self.recorder, self.__class__.response_text)
        self.closed = False
        self.__class__.instances.append(self)

    async def __aenter__(self) -> _FakeAsyncOpenAI:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self.closed = True


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
            ),
            "https://api.openai.com/v1",
            "sk-test",
            "gpt-4.1-mini",
        ),
        (
            Settings(
                ai_provider="ollama",
                ollama_openai_base_url="http://ollama:11434/v1",
                ollama_chat_model="llama3.2:1b",
                ollama_embed_model="nomic-embed-text",
            ),
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
    _FakeAsyncOpenAI.instances.clear()
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
    assert client.recorder["model"] == expected_model
    assert client.recorder["instructions"] == llm.SYSTEM_PROMPT
    assert client.recorder["input"] == "CONTEXT:\nalpha facts\n\nQUESTION:\nWhat does alpha say?"


def test_build_openai_client_uses_ollama_openai_compatible_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _FakeAsyncOpenAI.instances.clear()
    monkeypatch.setattr(llm, "AsyncOpenAI", _FakeAsyncOpenAI)

    client = llm.build_openai_client(
        Settings(
            ai_provider="ollama",
            ollama_openai_base_url="http://ollama:11434/v1",
            ollama_chat_model="llama3.2:1b",
            ollama_embed_model="nomic-embed-text",
        )
    )

    assert isinstance(client, _FakeAsyncOpenAI)
    assert client.base_url == "http://ollama:11434/v1"
    assert client.api_key == "ollama"


@pytest.mark.asyncio
async def test_generate_answer_returns_safe_fallback_when_content_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _FakeAsyncOpenAI.instances.clear()
    _FakeAsyncOpenAI.response_text = None
    monkeypatch.setattr(llm, "AsyncOpenAI", _FakeAsyncOpenAI)

    answer_text, model_used = await llm.generate_answer(
        "alpha facts",
        "What does alpha say?",
        settings=Settings(
            ai_provider="ollama",
            ollama_openai_base_url="http://ollama:11434/v1",
            ollama_chat_model="llama3.2:1b",
            ollama_embed_model="nomic-embed-text",
        ),
    )

    assert answer_text == "I don't know based on the uploaded documents."
    assert model_used == "response-model"
