from __future__ import annotations

from pathlib import Path

import pytest

from app.core.settings import Settings


def _write_secret_file(path: Path, value: str) -> str:
    path.write_text(value, encoding="utf-8")
    return str(path)


@pytest.fixture(autouse=True)
def clear_email_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for env_var in [
        "RESEND_API_KEY",
        "RESEND_API_KEY_FILE",
        "SMTP_PASSWORD",
        "SMTP_PASSWORD_FILE",
    ]:
        monkeypatch.delenv(env_var, raising=False)


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


def test_resend_api_key_file_takes_precedence_over_inline_value(tmp_path: Path) -> None:
    key_file = _write_secret_file(tmp_path / "resend_api_key.txt", "  re-from-file  \n")
    settings = Settings(
        app_env="production",
        secret_key="s" * 40,
        resend_api_key="re-from-env",
        resend_api_key_file=key_file,
        _env_file=None,
    )

    assert settings.resend_api_key is not None
    assert settings.resend_api_key.get_secret_value() == "re-from-file"


def test_secret_key_file_takes_precedence_over_inline_value(tmp_path: Path) -> None:
    key_file = _write_secret_file(tmp_path / "secret_key.txt", "  secret-from-file  \n")
    settings = Settings(
        secret_key="secret-from-env",
        secret_key_file=key_file,
        _env_file=None,
    )

    assert settings.secret_key is not None
    assert settings.secret_key.get_secret_value() == "secret-from-file"


def test_secret_key_file_satisfies_non_local_env(tmp_path: Path) -> None:
    secret_value = "s" * 40
    key_file = _write_secret_file(tmp_path / "secret_key.txt", f"  {secret_value}  \n")

    settings = Settings(app_env="docker", secret_key_file=key_file, _env_file=None)

    assert settings.secret_key is not None
    assert settings.secret_key.get_secret_value() == secret_value


def test_local_settings_use_development_secret_when_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("SECRET_KEY_FILE", raising=False)

    settings = Settings(app_env="local", _env_file=None)

    assert settings.secret_key is not None
    assert settings.secret_key.get_secret_value()


def test_secret_key_required_outside_local_or_test(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("SECRET_KEY_FILE", raising=False)

    with pytest.raises(ValueError, match="SECRET_KEY or SECRET_KEY_FILE"):
        Settings(app_env="production", _env_file=None)


def test_secret_key_must_be_long_enough_outside_local_or_test() -> None:
    with pytest.raises(ValueError, match="SECRET_KEY must be at least 32 characters"):
        Settings(app_env="production", secret_key="short", _env_file=None)


def test_secret_key_is_redacted_from_settings_repr() -> None:
    secret_value = "a" * 40
    settings = Settings(secret_key=secret_value, _env_file=None)

    assert secret_value not in repr(settings)


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

    assert (
        settings.get_database_url()
        == "postgresql+asyncpg://postgres:postgres-secret@db:5432/app_db"
    )


def test_smtp_password_file_takes_precedence_over_inline_value(tmp_path: Path) -> None:
    password_file = _write_secret_file(tmp_path / "smtp_password.txt", "  smtp-from-file  \n")
    settings = Settings(
        app_env="local",
        smtp_username="sourcewise",
        smtp_password="smtp-from-env",
        smtp_password_file=password_file,
        _env_file=None,
    )

    assert settings.smtp_password is not None
    assert settings.smtp_password.get_secret_value() == "smtp-from-file"


@pytest.mark.parametrize("app_env", ["test", "testing"])
def test_test_env_does_not_require_resend_or_smtp(app_env: str) -> None:
    settings = Settings(
        app_env=app_env,
        smtp_host="",
        resend_api_key=None,
        resend_api_key_file="missing-resend-key.txt",
        smtp_password_file="missing-smtp-password.txt",
        _env_file=None,
    )

    assert settings.app_env == app_env
    assert settings.resend_api_key is None


@pytest.mark.parametrize("app_env", ["local", "docker"])
def test_smtp_env_requires_smtp_host(app_env: str) -> None:
    kwargs = {"app_env": app_env, "smtp_host": "", "_env_file": None}
    if app_env == "docker":
        kwargs["secret_key"] = "s" * 40

    with pytest.raises(ValueError, match="SMTP_HOST"):
        Settings(**kwargs)


@pytest.mark.parametrize("app_env", ["staging", "production"])
def test_resend_env_requires_api_key_or_key_file(
    app_env: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.delenv("RESEND_API_KEY_FILE", raising=False)

    with pytest.raises(ValueError, match="RESEND_API_KEY or RESEND_API_KEY_FILE"):
        Settings(app_env=app_env, secret_key="s" * 40, _env_file=None)


@pytest.mark.parametrize("app_env", ["staging", "production"])
def test_resend_env_accepts_inline_api_key(app_env: str) -> None:
    settings = Settings(
        app_env=app_env,
        secret_key="s" * 40,
        resend_api_key="re-api-key",
        _env_file=None,
    )

    assert settings.resend_api_key is not None
    assert settings.resend_api_key.get_secret_value() == "re-api-key"


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


def test_ollama_provider_does_not_read_openai_key_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    missing_key_file = tmp_path / "missing-openai-key.txt"
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    settings = Settings(
        ai_provider="ollama",
        openai_api_key_file=str(missing_key_file),
        ollama_openai_base_url="http://ollama:11434/v1",
        ollama_chat_model="llama3.2:1b",
        ollama_embed_model="nomic-embed-text",
        _env_file=None,
    )

    assert settings.openai_api_key is None
