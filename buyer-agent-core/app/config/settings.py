from __future__ import annotations

from enum import Enum
from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProvider(str, Enum):
    OPENAI = "openai"
    GEMINI = "gemini"
    LOCAL = "local"


class Settings(BaseSettings):
    """Centralized configuration for the Buyer Agent, populated from
    environment variables (and a local .env during development). Mirrors
    merchant-agent-core/app/config/settings.py so the two services share
    the same operational shape.
    """

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[2] / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    # --- LLM (the Buyer Agent's own reasoning model) ---
    llm_provider: LLMProvider = Field(default=LLMProvider.GEMINI, alias="LLM_PROVIDER")
    llm_model: str = Field(default="gemini-flash-latest", alias="LLM_MODEL")
    llm_api_key: str = Field(default="", alias="LLM_API_KEY")
    llm_base_url: str = Field(default="https://api.openai.com/v1", alias="LLM_BASE_URL")
    gemini_api_key: str = Field(
        default="", alias="GEMINI_API_KEY", validation_alias=AliasChoices("GEMINI_API_KEY")
    )
    gemini_base_url: str = Field(
        default="https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent",
        alias="GEMINI_BASE_URL",
    )
    llm_max_output_tokens: int = Field(default=128, alias="LLM_MAX_OUTPUT_TOKENS")

    # --- Talking to merchant agents ---
    # Per-call timeout to a single merchant agent. Kept short: the whole
    # point of fanning out to several shops is to stay fast, so one slow
    # merchant must not stall the others or the user.
    merchant_timeout_seconds: float = Field(default=12.0, alias="MERCHANT_TIMEOUT_SECONDS")
    # Cap on how many merchants get contacted in parallel for one search.
    max_parallel_merchants: int = Field(default=6, alias="MAX_PARALLEL_MERCHANTS")
    # How many merchants to shortlist from the registry before contacting any.
    max_merchants_per_query: int = Field(default=4, alias="MAX_MERCHANTS_PER_QUERY")

    agent_max_iterations: int = Field(default=8, alias="AGENT_MAX_ITERATIONS")

    # --- Persistence (Postgres) ---
    database_url: str = Field(..., alias="DATABASE_URL")
    # e.g. postgresql+psycopg://buyer_agent:password@localhost:5432/buyer_agent

    # --- Registry encryption ---
    # Fernet key (32 url-safe base64 bytes). Generate with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    registry_encryption_key: str = Field(..., alias="REGISTRY_ENCRYPTION_KEY")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    dashboard_cors_origins: str = Field(default="http://localhost:5173", alias="BUYER_CORS_ORIGINS")


@lru_cache
def get_settings() -> Settings:
    """Cached Settings instance - construct once per process."""
    return Settings()
