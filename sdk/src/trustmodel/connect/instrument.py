"""One-line instrumentation for AI agents."""

from __future__ import annotations

import asyncio
import atexit
from dataclasses import dataclass
from typing import Any, Callable, Optional
from uuid import UUID

from trustmodel.api.client import TrustModelClient, get_client
from trustmodel.connect.tracer import Tracer, get_tracer
from trustmodel.connect.exporters import BatchTraceExporter
from trustmodel.core.config import TrustModelConfig, configure, get_config
from trustmodel.core.exceptions import ConfigurationError
from trustmodel.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class InstrumentHandle:
    """Handle returned from instrument() for managing instrumentation."""

    agent_id: UUID
    agent_name: str
    tracer: Tracer
    exporter: BatchTraceExporter
    _shutdown_registered: bool = False

    def shutdown(self) -> None:
        """Shutdown instrumentation and flush pending traces."""
        logger.info("Shutting down instrumentation", agent_id=str(self.agent_id))
        asyncio.get_event_loop().run_until_complete(self._async_shutdown())

    async def _async_shutdown(self) -> None:
        """Async shutdown."""
        await self.exporter.flush()
        await self.exporter.shutdown()

    def __enter__(self) -> "InstrumentHandle":
        return self

    def __exit__(self, *args: Any) -> None:
        self.shutdown()


async def _register_or_get_agent(
    client: TrustModelClient,
    config: TrustModelConfig,
) -> tuple[UUID, str]:
    """Register agent or get existing agent ID."""
    # If agent_id is provided, verify it exists
    if config.agent_id:
        try:
            agent = await client.get_agent(UUID(config.agent_id))
            return UUID(agent["id"]), agent["name"]
        except Exception as e:
            logger.warning(f"Could not get agent {config.agent_id}: {e}")

    # Register new agent
    if not config.agent_name:
        raise ConfigurationError(
            "Either agent_name or agent_id must be provided",
            missing_fields=["agent_name", "agent_id"],
        )

    try:
        agent = await client.register_agent({
            "name": config.agent_name,
            "agent_type": "custom",
            "metadata": {
                "sdk_version": "0.1.0",
                "auto_registered": True,
            },
        })
        logger.info("Registered new agent", agent_id=agent["id"], name=agent["name"])
        return UUID(agent["id"]), agent["name"]
    except Exception as e:
        # If registration fails (e.g., already exists), try to find by name
        logger.warning(f"Could not register agent: {e}")
        agents = await client.list_agents()
        for agent in agents.get("items", []):
            if agent["name"] == config.agent_name:
                return UUID(agent["id"]), agent["name"]
        raise ConfigurationError(f"Could not register or find agent: {config.agent_name}")


def instrument(
    agent_name: Optional[str] = None,
    api_key: Optional[str] = None,
    server_url: Optional[str] = None,
    agent_id: Optional[str] = None,
    auto_detect: bool = True,
    **kwargs: Any,
) -> InstrumentHandle:
    """
    Instrument an AI agent for tracing and evaluation.

    This is the main entry point for the TrustModel SDK. Call this once
    at the start of your agent to enable automatic tracing.

    Args:
        agent_name: Name of the agent (used for registration if agent_id not provided)
        api_key: TrustModel API key (can also be set via TRUSTMODEL_API_KEY env var)
        server_url: TrustModel server URL (defaults to https://api.trustmodel.dev)
        agent_id: Existing agent ID (if already registered)
        auto_detect: Automatically detect and patch LLM libraries (default True)
        **kwargs: Additional configuration options

    Returns:
        InstrumentHandle for managing the instrumentation

    Example:
        from trustmodel import instrument

        handle = instrument(
            agent_name="my-agent",
            api_key="tm_..."
        )

        # Your agent code here
        # All LLM calls are automatically traced

        handle.shutdown()  # Flush traces before exit
    """
    # Configure SDK
    config = configure(
        server_url=server_url,
        api_key=api_key,
        agent_name=agent_name,
        agent_id=agent_id,
        **kwargs,
    )

    if not config.api_key:
        raise ConfigurationError(
            "API key is required. Set TRUSTMODEL_API_KEY or pass api_key parameter.",
            missing_fields=["api_key"],
        )

    # Create client and register agent
    client = get_client()

    # Run async registration
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        registered_id, registered_name = loop.run_until_complete(
            _register_or_get_agent(client, config)
        )
    finally:
        loop.close()

    # Create tracer and exporter
    exporter = BatchTraceExporter(
        client=client,
        agent_id=registered_id,
        batch_size=config.trace_batch_size,
        export_interval=config.trace_export_interval,
    )

    tracer = Tracer(
        agent_id=registered_id,
        agent_name=registered_name,
        exporter=exporter,
        sample_rate=config.trace_sample_rate,
    )

    # Auto-detect and patch LLM libraries
    if auto_detect:
        _auto_patch_libraries(tracer)

    # Create handle
    handle = InstrumentHandle(
        agent_id=registered_id,
        agent_name=registered_name,
        tracer=tracer,
        exporter=exporter,
    )

    # Register shutdown handler
    def _shutdown() -> None:
        try:
            handle.shutdown()
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

    atexit.register(_shutdown)
    handle._shutdown_registered = True

    logger.info(
        "Agent instrumented",
        agent_id=str(registered_id),
        agent_name=registered_name,
        auto_detect=auto_detect,
    )

    return handle


def _auto_patch_libraries(tracer: Tracer) -> None:
    """Auto-detect and patch LLM libraries."""
    # Try to patch Anthropic
    try:
        from trustmodel.connect.auto.anthropic import patch_anthropic
        patch_anthropic(tracer)
        logger.info("Patched Anthropic client")
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"Could not patch Anthropic: {e}")

    # Try to patch OpenAI
    try:
        from trustmodel.connect.auto.openai import patch_openai
        patch_openai(tracer)
        logger.info("Patched OpenAI client")
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"Could not patch OpenAI: {e}")

    # Try to patch LangChain
    try:
        from trustmodel.connect.auto.langchain import patch_langchain
        patch_langchain(tracer)
        logger.info("Patched LangChain")
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"Could not patch LangChain: {e}")
