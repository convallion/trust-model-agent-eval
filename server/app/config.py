"""Application configuration using pydantic-settings."""

from functools import lru_cache
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ═══════════════════════════════════════════════════════════════════════════
    # Application
    # ═══════════════════════════════════════════════════════════════════════════
    app_name: str = "TrustModel Agent Eval"
    app_version: str = "0.1.0"
    debug: bool = False
    log_level: str = "INFO"

    # ═══════════════════════════════════════════════════════════════════════════
    # Database
    # ═══════════════════════════════════════════════════════════════════════════
    database_url: str = Field(
        default="postgresql+asyncpg://trustmodel:trustmodel@localhost:5432/trustmodel",
        description="PostgreSQL connection URL",
    )

    # ═══════════════════════════════════════════════════════════════════════════
    # Redis
    # ═══════════════════════════════════════════════════════════════════════════
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
    )

    # ═══════════════════════════════════════════════════════════════════════════
    # Security
    # ═══════════════════════════════════════════════════════════════════════════
    secret_key: str = Field(
        default="your-secret-key-change-in-production",
        description="Secret key for JWT signing",
    )
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440  # 24 hours for development

    # CORS
    allowed_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:3001", "http://localhost:8000"],
        description="Allowed CORS origins",
    )

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, v: str | List[str]) -> List[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    # ═══════════════════════════════════════════════════════════════════════════
    # Certificate Authority
    # ═══════════════════════════════════════════════════════════════════════════
    root_ca_private_key: Optional[str] = Field(
        default=None,
        description="Base64-encoded Ed25519 private key for Root CA",
    )
    certificate_validity_days: int = Field(
        default=90,
        description="Certificate validity period in days",
    )
    ca_keys_dir: str = Field(
        default="./ca_keys",
        description="Directory to store CA keys",
    )

    # ═══════════════════════════════════════════════════════════════════════════
    # LLM Provider (for Model-as-Judge)
    # ═══════════════════════════════════════════════════════════════════════════
    anthropic_api_key: Optional[str] = Field(
        default=None,
        description="Anthropic API key for evaluation grading",
    )
    grading_model: str = Field(
        default="claude-sonnet-4-5-20250929",
        description="Model to use for LLM-as-judge grading",
    )

    # ═══════════════════════════════════════════════════════════════════════════
    # OpenRouter (for LLM-as-Judge via OpenRouter)
    # ═══════════════════════════════════════════════════════════════════════════
    openrouter_api_key: Optional[str] = Field(
        default=None,
        description="OpenRouter API key for LLM grading",
    )
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        description="OpenRouter API base URL",
    )
    openrouter_model: str = Field(
        default="anthropic/claude-3-opus",
        description="OpenRouter model to use for grading",
    )
    openrouter_timeout_seconds: int = Field(
        default=120,
        description="Timeout for OpenRouter API calls in seconds",
    )
    openrouter_max_retries: int = Field(
        default=3,
        description="Maximum retries for OpenRouter API calls",
    )

    # ═══════════════════════════════════════════════════════════════════════════
    # LangSmith / LangGraph (for evaluating LangSmith agents)
    # ═══════════════════════════════════════════════════════════════════════════
    langsmith_api_key: Optional[str] = Field(
        default=None,
        description="LangSmith API key for agent evaluation",
    )
    langsmith_api_url: Optional[str] = Field(
        default=None,
        description="LangSmith/LangGraph agent API URL",
    )

    # ═══════════════════════════════════════════════════════════════════════════
    # Evaluation
    # ═══════════════════════════════════════════════════════════════════════════
    max_eval_concurrency: int = Field(
        default=5,
        description="Maximum concurrent evaluation tasks",
    )
    eval_timeout_minutes: int = Field(
        default=60,
        description="Evaluation timeout in minutes",
    )

    # ═══════════════════════════════════════════════════════════════════════════
    # API Keys
    # ═══════════════════════════════════════════════════════════════════════════
    api_key_prefix: str = "tm_"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
