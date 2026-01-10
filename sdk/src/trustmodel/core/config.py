"""SDK Configuration management."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class TrustModelConfig(BaseSettings):
    """TrustModel SDK configuration."""

    model_config = SettingsConfigDict(
        env_prefix="TRUSTMODEL_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Server connection
    server_url: str = Field(
        default="https://api.trustmodel.dev",
        description="TrustModel server URL",
    )
    api_key: Optional[str] = Field(
        default=None,
        description="API key for authentication",
    )

    # Agent identification
    agent_name: Optional[str] = Field(
        default=None,
        description="Name of the agent being instrumented",
    )
    agent_id: Optional[str] = Field(
        default=None,
        description="UUID of a registered agent",
    )

    # Tracing configuration
    tracing_enabled: bool = Field(
        default=True,
        description="Enable trace collection",
    )
    trace_sample_rate: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Sampling rate for traces (0.0 to 1.0)",
    )
    trace_batch_size: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Number of spans to batch before export",
    )
    trace_export_interval: float = Field(
        default=5.0,
        ge=0.1,
        description="Interval in seconds between trace exports",
    )

    # Proxy configuration
    proxy_enabled: bool = Field(
        default=False,
        description="Enable LLM proxy for automatic tracing",
    )
    proxy_port: int = Field(
        default=8080,
        ge=1024,
        le=65535,
        description="Port for the local proxy server",
    )

    # Logging
    log_level: str = Field(
        default="INFO",
        description="Logging level",
    )
    log_format: str = Field(
        default="json",
        description="Log format (json or console)",
    )

    # Timeouts
    request_timeout: float = Field(
        default=30.0,
        ge=1.0,
        description="HTTP request timeout in seconds",
    )
    websocket_timeout: float = Field(
        default=60.0,
        ge=1.0,
        description="WebSocket connection timeout in seconds",
    )

    # Retry configuration
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum number of retry attempts",
    )
    retry_delay: float = Field(
        default=1.0,
        ge=0.1,
        description="Initial delay between retries in seconds",
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return upper

    @field_validator("log_format")
    @classmethod
    def validate_log_format(cls, v: str) -> str:
        """Validate log format."""
        valid_formats = {"json", "console"}
        lower = v.lower()
        if lower not in valid_formats:
            raise ValueError(f"Invalid log format: {v}. Must be one of {valid_formats}")
        return lower

    def is_configured(self) -> bool:
        """Check if SDK is properly configured with required settings."""
        return bool(self.api_key and (self.agent_name or self.agent_id))


@lru_cache()
def get_config() -> TrustModelConfig:
    """Get cached SDK configuration."""
    return TrustModelConfig()


def configure(
    server_url: Optional[str] = None,
    api_key: Optional[str] = None,
    agent_name: Optional[str] = None,
    agent_id: Optional[str] = None,
    **kwargs,
) -> TrustModelConfig:
    """
    Configure the SDK programmatically.

    This clears the cached config and creates a new one with the provided settings.
    Environment variables and .env file are still read, but explicit parameters take precedence.
    """
    # Clear the cache
    get_config.cache_clear()

    # Set environment variables for the parameters
    if server_url:
        os.environ["TRUSTMODEL_SERVER_URL"] = server_url
    if api_key:
        os.environ["TRUSTMODEL_API_KEY"] = api_key
    if agent_name:
        os.environ["TRUSTMODEL_AGENT_NAME"] = agent_name
    if agent_id:
        os.environ["TRUSTMODEL_AGENT_ID"] = agent_id

    for key, value in kwargs.items():
        env_key = f"TRUSTMODEL_{key.upper()}"
        os.environ[env_key] = str(value)

    return get_config()
