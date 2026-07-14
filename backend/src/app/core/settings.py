"""Application settings."""

from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import quote_plus

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_LOCAL_APP_ENVS = {"local", "test", "testing"}
_EMAIL_SMTP_APP_ENVS = {"local", "docker"}
_EMAIL_RESEND_APP_ENVS = {"staging", "production"}
_LOCAL_SECRET_KEY = "sourcewise-local-test-secret-key-do-not-use-in-production"
_MIN_SECRET_KEY_LENGTH = 32


def _read_secret_file(path: str, *, env_var_name: str) -> str:
    """Read and normalize a secret value from disk."""
    try:
        content = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"{env_var_name} points to an unreadable file: {path}") from exc

    value = content.strip()
    if not value:
        raise ValueError(f"{env_var_name} points to an empty file: {path}")
    return value


class Settings(BaseSettings):
    """Runtime application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = "local"
    app_title: str = "Sourcewise API"
    app_version: str = "0.1.0"
    log_level: str = "INFO"
    secret_key: SecretStr | None = None
    secret_key_file: str | None = None
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=30, gt=0)
    email_verification_token_expire_minutes: int = Field(default=1440, gt=0)
    password_reset_token_expire_minutes: int = Field(default=60, gt=0)
    app_base_url: str = "http://localhost:8000"
    frontend_base_url: str = "http://localhost:3000"
    email_from: str = "Sourcewise <no-reply@notifications.ibrahimherawi.com>"
    resend_api_key: SecretStr | None = None
    resend_api_key_file: str | None = None
    smtp_host: str = "mailpit"
    smtp_port: int = Field(default=1025, gt=0, le=65535)
    smtp_use_tls: bool = False
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_password_file: str | None = None
    postgres_host: str = "localhost"
    postgres_port: int = Field(default=5432, gt=0, le=65535)
    postgres_user: str = "postgres"
    postgres_db: str = "app_db"
    postgres_password: SecretStr | None = None
    postgres_password_file: str | None = None
    embedding_dim: int = 768
    ingest_workers: int = Field(default=2, gt=0)
    ingest_shutdown_timeout_s: float = Field(default=30.0, gt=0)
    chunk_size_chars: int = Field(default=2000, gt=0)
    chunk_overlap_chars: int = Field(default=100, ge=0)
    retrieval_max_cosine_distance: float = Field(default=0.75, ge=0.0, le=2.0)
    top_k: int = Field(default=5, gt=0)

    ai_provider: Literal["openai", "ollama"] = "ollama"

    openai_api_key: SecretStr | None = None
    openai_api_key_file: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_chat_model: str | None = None

    ollama_openai_base_url: str = "http://localhost:11434/v1"
    ollama_chat_model: str = "llama3.2:1b"
    ollama_embed_model: str = "nomic-embed-text"
    embed_concurrency: int = Field(default=4, gt=0)
    ollama_embed_batch_size: int = Field(default=32, ge=1, le=128)
    ollama_embed_connect_timeout_s: float = Field(default=5.0, gt=0)
    ollama_embed_read_timeout_s: float = Field(default=120.0, gt=0)
    ollama_embed_max_connections: int = Field(default=20, gt=0)
    ollama_embed_max_keepalive_connections: int = Field(default=10, ge=0)
    ollama_embed_retry_attempts: int = Field(default=3, ge=1)
    ollama_embed_retry_min_wait_s: float = Field(default=0.2, gt=0)
    ollama_embed_retry_max_wait_s: float = Field(default=2.0, gt=0)
    max_upload_mb: int = Field(default=10, gt=0)
    upload_root_dir: str = "/data/uploads"

    @staticmethod
    def _resolve_secret(
        *,
        inline_secret: SecretStr | None,
        file_path: str | None,
        inline_env_name: str,
        file_env_name: str,
    ) -> SecretStr | None:
        if file_path:
            return SecretStr(_read_secret_file(file_path, env_var_name=file_env_name))

        if inline_secret is None:
            return None

        normalized = inline_secret.get_secret_value().strip()
        if not normalized:
            return None
        return SecretStr(normalized)

    @model_validator(mode="after")
    def validate_provider_requirements(self) -> "Settings":
        """Validate required runtime settings."""
        self.app_env = self.app_env.strip()
        self.jwt_algorithm = self.jwt_algorithm.strip()
        self.app_base_url = self.app_base_url.strip()
        self.frontend_base_url = self.frontend_base_url.strip()
        self.email_from = self.email_from.strip()
        self.smtp_host = self.smtp_host.strip()
        smtp_username = self.smtp_username.strip() if self.smtp_username else ""
        self.smtp_username = smtp_username or None

        if not self.app_env:
            raise ValueError("APP_ENV must not be empty.")
        if not self.jwt_algorithm:
            raise ValueError("JWT_ALGORITHM must not be empty.")
        if not self.app_base_url:
            raise ValueError("APP_BASE_URL must not be empty.")
        if not self.frontend_base_url:
            raise ValueError("FRONTEND_BASE_URL must not be empty.")
        if not self.email_from:
            raise ValueError("EMAIL_FROM must not be empty.")

        normalized_app_env = self.app_env.lower()
        is_local_env = normalized_app_env in _LOCAL_APP_ENVS
        self.secret_key = self._resolve_secret(
            inline_secret=self.secret_key,
            file_path=self.secret_key_file,
            inline_env_name="SECRET_KEY",
            file_env_name="SECRET_KEY_FILE",
        )
        if self.secret_key is None:
            if is_local_env:
                self.secret_key = SecretStr(_LOCAL_SECRET_KEY)
            else:
                raise ValueError(
                    "SECRET_KEY or SECRET_KEY_FILE must be set when APP_ENV is not local/test."
                )
        elif not is_local_env:
            secret_key_value = self.secret_key.get_secret_value()
            if secret_key_value == _LOCAL_SECRET_KEY:
                raise ValueError(
                    "SECRET_KEY must not use the local/test default when APP_ENV is not local/test."
                )
            if len(secret_key_value) < _MIN_SECRET_KEY_LENGTH:
                raise ValueError(
                    "SECRET_KEY must be at least 32 characters when APP_ENV is not local/test."
                )

        self.postgres_password = self._resolve_secret(
            inline_secret=self.postgres_password,
            file_path=self.postgres_password_file,
            inline_env_name="POSTGRES_PASSWORD",
            file_env_name="POSTGRES_PASSWORD_FILE",
        )
        if self.ai_provider == "openai":
            self.openai_api_key = self._resolve_secret(
                inline_secret=self.openai_api_key,
                file_path=self.openai_api_key_file,
                inline_env_name="OPENAI_API_KEY",
                file_env_name="OPENAI_API_KEY_FILE",
            )
        elif self.openai_api_key is not None:
            normalized = self.openai_api_key.get_secret_value().strip()
            self.openai_api_key = SecretStr(normalized) if normalized else None

        if normalized_app_env in _EMAIL_RESEND_APP_ENVS:
            self.resend_api_key = self._resolve_secret(
                inline_secret=self.resend_api_key,
                file_path=self.resend_api_key_file,
                inline_env_name="RESEND_API_KEY",
                file_env_name="RESEND_API_KEY_FILE",
            )
        elif self.resend_api_key is not None:
            normalized = self.resend_api_key.get_secret_value().strip()
            self.resend_api_key = SecretStr(normalized) if normalized else None

        if normalized_app_env in _EMAIL_SMTP_APP_ENVS:
            self.smtp_password = self._resolve_secret(
                inline_secret=self.smtp_password,
                file_path=self.smtp_password_file,
                inline_env_name="SMTP_PASSWORD",
                file_env_name="SMTP_PASSWORD_FILE",
            )
        elif self.smtp_password is not None:
            normalized = self.smtp_password.get_secret_value().strip()
            self.smtp_password = SecretStr(normalized) if normalized else None

        self.postgres_host = self.postgres_host.strip()
        self.postgres_user = self.postgres_user.strip()
        self.postgres_db = self.postgres_db.strip()
        self.openai_base_url = self.openai_base_url.strip()
        self.ollama_openai_base_url = self.ollama_openai_base_url.strip()

        if not self.postgres_host:
            raise ValueError("POSTGRES_HOST must be set.")
        if not self.postgres_user:
            raise ValueError("POSTGRES_USER must be set.")
        if not self.postgres_db:
            raise ValueError("POSTGRES_DB must be set.")

        if normalized_app_env in _EMAIL_RESEND_APP_ENVS and self.resend_api_key is None:
            raise ValueError(
                "RESEND_API_KEY or RESEND_API_KEY_FILE must be set when APP_ENV is "
                "staging or production."
            )
        if normalized_app_env in _EMAIL_SMTP_APP_ENVS and not self.smtp_host:
            raise ValueError("SMTP_HOST must be set when APP_ENV is local or docker.")

        if self.ai_provider == "openai":
            if not self.openai_api_key:
                raise ValueError("OPENAI_API_KEY must be set when AI_PROVIDER=openai.")
            if not self.openai_base_url.strip():
                raise ValueError("OPENAI_BASE_URL must be set when AI_PROVIDER=openai.")
            if not self.openai_chat_model:
                raise ValueError("OPENAI_CHAT_MODEL must be set when AI_PROVIDER=openai.")

        if self.ai_provider == "ollama":
            if not self.ollama_openai_base_url:
                raise ValueError("OLLAMA_OPENAI_BASE_URL must be set when AI_PROVIDER=ollama.")
            if not self.ollama_chat_model:
                raise ValueError("OLLAMA_CHAT_MODEL must be set when AI_PROVIDER=ollama.")
            if not self.ollama_embed_model:
                raise ValueError("OLLAMA_EMBED_MODEL must be set when AI_PROVIDER=ollama.")

        if not self.upload_root_dir.strip():
            raise ValueError("UPLOAD_ROOT_DIR must not be empty.")

        if self.chunk_overlap_chars >= self.chunk_size_chars:
            raise ValueError("CHUNK_OVERLAP_CHARS must be less than CHUNK_SIZE_CHARS.")

        if self.ollama_embed_retry_max_wait_s < self.ollama_embed_retry_min_wait_s:
            raise ValueError(
                "OLLAMA_EMBED_RETRY_MAX_WAIT_S must be greater than or equal to "
                "OLLAMA_EMBED_RETRY_MIN_WAIT_S."
            )

        return self

    def get_database_url(self) -> str:
        """Return the runtime database URL assembled from connection components."""
        if self.postgres_password is None:
            raise ValueError(
                "POSTGRES_PASSWORD or POSTGRES_PASSWORD_FILE must be set to build the database URL."
            )

        quoted_user = quote_plus(self.postgres_user)
        quoted_password = quote_plus(self.postgres_password.get_secret_value())
        quoted_database = quote_plus(self.postgres_db)
        return (
            f"postgresql+asyncpg://{quoted_user}:{quoted_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{quoted_database}"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings."""
    return Settings()
