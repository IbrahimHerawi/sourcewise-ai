"""Application settings."""

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, model_validator
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

    ai_provider: Literal["openai", "ollama"] = "ollama"

    openai_api_key: SecretStr | None = None
    openai_chat_model: str | None = None

    ollama_openai_base_url: str = "http://localhost:11434/v1"
    ollama_chat_model: str = "llama3.2:1b"

    @model_validator(mode="after")
    def validate_provider_requirements(self) -> "Settings":
        """Validate provider-specific required settings."""
        if self.ai_provider == "openai":
            if not self.openai_api_key:
                raise ValueError("OPENAI_API_KEY must be set when AI_PROVIDER=openai.")
            if not self.openai_chat_model:
                raise ValueError("OPENAI_CHAT_MODEL must be set when AI_PROVIDER=openai.")

        if self.ai_provider == "ollama":
            if not self.ollama_openai_base_url:
                raise ValueError("OLLAMA_OPENAI_BASE_URL must be set when AI_PROVIDER=ollama.")
            if not self.ollama_chat_model:
                raise ValueError("OLLAMA_CHAT_MODEL must be set when AI_PROVIDER=ollama.")

        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings."""
    return Settings()
