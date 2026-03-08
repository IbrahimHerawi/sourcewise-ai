"""Application settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/app_db"
    embedding_dim: int = 768
    ingest_workers: int = Field(default=2, gt=0)
    chunk_size_chars: int = Field(default=1200, gt=0)
    chunk_overlap_chars: int = Field(default=200, ge=0)
    retrieval_max_cosine_distance: float = Field(default=0.75, ge=0.0, le=2.0)

    ai_provider: Literal["openai", "ollama"] = "ollama"

    openai_api_key: SecretStr | None = None
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

    @model_validator(mode="after")
    def validate_provider_requirements(self) -> "Settings":
        """Validate provider-specific required settings."""
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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings."""
    return Settings()
