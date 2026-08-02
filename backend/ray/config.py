"""Application configuration.

Every setting comes from the environment (ADR-0012). Nothing is hardcoded and no
secret ever lives in source.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RAY_",
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: Literal["development", "production"] = "development"
    host: str = "127.0.0.1"
    port: int = 8000

    # Single-user bearer token (ADR-0006).
    api_token: str = "change-me"

    database_url: str = "postgresql+asyncpg://ray:ray@localhost:5433/ray"

    user_name: str = "Ray User"
    user_email: str | None = None
    user_timezone: str = "UTC"

    # LLM provider selection (ADR-0001). Adapters arrive in Phase 2; the settings
    # exist now so the contract is fixed and nothing hardcodes a provider later.
    llm_provider: Literal["gemini", "groq", "ollama"] = "gemini"
    llm_router_provider: Literal["gemini", "groq", "ollama"] | None = None
    llm_fallback_provider: Literal["gemini", "groq", "ollama"] | None = None

    # Local embeddings (ADR-0003). The dimension must match the vector column.
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dim: int = 384

    # Voice (ADR-0009). Browser backends work with zero setup; local backends
    # (faster-whisper, Piper) land in Phase 6.
    stt_backend: Literal["browser", "local"] = "browser"
    tts_backend: Literal["browser", "local"] = "browser"
    wake_word_enabled: bool = False

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    @property
    def is_development(self) -> bool:
        return self.env == "development"


@lru_cache
def get_settings() -> Settings:
    """Cached so configuration is read once per process."""
    return Settings()
