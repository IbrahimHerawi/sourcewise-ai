"""Application settings."""

from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import quote_plus

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    app_title: str = "Backend Technical Evaluation API"
    app_version: str = "0.1.0"
    log_level: str = "INFO"
    postgres_host: str = "localhost"
    postgres_port: int = Field(default=5432, gt=0, le=65535)
    postgres_user: str = "postgres"
    postgres_db: str = "app_db"
    postgres_password: SecretStr | None = None
    postgres_password_file: str | None = None
    embedding_dim: int = 768
    ingest_workers: int = Field(default=2, gt=0)
    chunk_size_chars: int = Field(default=1200, gt=0)
    chunk_overlap_chars: int = Field(default=200, ge=0)
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
    ollama_embed_connect_timeout_s: float = Field(default=5.0, gt=0)
    ollama_embed_read_timeout_s: float = Field(default=30.0, gt=0)
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
        """Validate provider-specific required settings."""
        self.openai_api_key = self._resolve_secret(
            inline_secret=self.openai_api_key,
            file_path=self.openai_api_key_file,
            inline_env_name="OPENAI_API_KEY",
            file_env_name="OPENAI_API_KEY_FILE",
        )
        self.postgres_password = self._resolve_secret(
            inline_secret=self.postgres_password,
            file_path=self.postgres_password_file,
            inline_env_name="POSTGRES_PASSWORD",
            file_env_name="POSTGRES_PASSWORD_FILE",
        )

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
