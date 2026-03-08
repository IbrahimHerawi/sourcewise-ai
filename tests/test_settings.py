from __future__ import annotations

from pathlib import Path

import pytest

from app.core.settings import Settings


def _write_secret_file(path: Path, value: str) -> str:
    path.write_text(value, encoding="utf-8")
    return str(path)


def test_openai_api_key_file_takes_precedence_over_inline_value(tmp_path: Path) -> None:
    key_file = _write_secret_file(tmp_path / "openai_api_key.txt", "  sk-from-file  \n")
    settings = Settings(
        ai_provider="openai",
        openai_api_key="sk-from-env",
        openai_api_key_file=key_file,
        openai_base_url="https://api.openai.com/v1",
        openai_chat_model="gpt-4.1-mini",
        _env_file=None,
    )

    assert settings.openai_api_key is not None
    assert settings.openai_api_key.get_secret_value() == "sk-from-file"


def test_postgres_password_file_takes_precedence_and_db_url_is_assembled(tmp_path: Path) -> None:
    password_file = _write_secret_file(tmp_path / "postgres_password.txt", "  postgres-secret \n")
    settings = Settings(
        postgres_host="db",
        postgres_port=5432,
        postgres_user="postgres",
        postgres_db="app_db",
        postgres_password="from-env",
        postgres_password_file=password_file,
        _env_file=None,
    )

    assert settings.get_database_url() == "postgresql+asyncpg://postgres:postgres-secret@db:5432/app_db"


def test_get_database_url_requires_password(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    monkeypatch.delenv("POSTGRES_PASSWORD_FILE", raising=False)

    settings = Settings(
        postgres_host="db",
        postgres_port=5432,
        postgres_user="postgres",
        postgres_db="app_db",
        _env_file=None,
    )

    with pytest.raises(ValueError, match="POSTGRES_PASSWORD or POSTGRES_PASSWORD_FILE"):
        settings.get_database_url()
