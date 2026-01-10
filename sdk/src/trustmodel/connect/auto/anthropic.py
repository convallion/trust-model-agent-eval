"""Auto-instrumentation for Anthropic SDK."""

from __future__ import annotations

import functools
import time
from typing import TYPE_CHECKING, Any, Callable

from trustmodel.core.logging import get_logger
from trustmodel.models.trace import SpanType

if TYPE_CHECKING:
    from trustmodel.connect.tracer import Tracer

logger = get_logger(__name__)

_original_create: Callable[..., Any] | None = None
_original_create_async: Callable[..., Any] | None = None


def patch_anthropic(tracer: "Tracer") -> None:
    """Patch Anthropic SDK to automatically trace API calls."""
    global _original_create, _original_create_async

    try:
        import anthropic
    except ImportError:
        logger.debug("Anthropic SDK not installed, skipping patch")
        return

    # Patch synchronous messages.create
    if hasattr(anthropic, "Anthropic"):
        _patch_sync_client(anthropic.Anthropic, tracer)

    # Patch async messages.create
    if hasattr(anthropic, "AsyncAnthropic"):
        _patch_async_client(anthropic.AsyncAnthropic, tracer)

    logger.info("Anthropic SDK patched for tracing")


def _patch_sync_client(client_class: type, tracer: "Tracer") -> None:
    """Patch synchronous Anthropic client."""
    original_init = client_class.__init__

    @functools.wraps(original_init)
    def patched_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        _patch_messages_resource(self.messages, tracer, is_async=False)

    client_class.__init__ = patched_init


def _patch_async_client(client_class: type, tracer: "Tracer") -> None:
    """Patch async Anthropic client."""
    original_init = client_class.__init__

    @functools.wraps(original_init)
    def patched_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        _patch_messages_resource(self.messages, tracer, is_async=True)

    client_class.__init__ = patched_init


def _patch_messages_resource(messages: Any, tracer: "Tracer", is_async: bool) -> None:
    """Patch the messages resource."""
    original_create = messages.create

    if is_async:
        @functools.wraps(original_create)
        async def traced_create(*args: Any, **kwargs: Any) -> Any:
            return await _trace_anthropic_call(original_create, tracer, *args, **kwargs)
        messages.create = traced_create
    else:
        @functools.wraps(original_create)
        def traced_create(*args: Any, **kwargs: Any) -> Any:
            return _trace_anthropic_call_sync(original_create, tracer, *args, **kwargs)
        messages.create = traced_create


async def _trace_anthropic_call(
    original_fn: Callable[..., Any],
    tracer: "Tracer",
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Trace an async Anthropic API call."""
    model = kwargs.get("model", "unknown")
    messages = kwargs.get("messages", [])

    # Build prompt from messages
    prompt = _extract_prompt(messages)

    start_time = time.time()
    error_msg = None

    try:
        with tracer.span(f"anthropic:{model}", span_type=SpanType.llm_call) as span:
            span.set_attribute("model", model)
            span.set_attribute("provider", "anthropic")
            span.set_attribute("max_tokens", kwargs.get("max_tokens"))
            span.set_attribute("temperature", kwargs.get("temperature"))

            response = await original_fn(*args, **kwargs)

            # Extract response data
            content = _extract_response_content(response)
            usage = getattr(response, "usage", None)

            span.set_attribute("response", content[:1000] if content else None)
            if usage:
                span.set_attribute("input_tokens", usage.input_tokens)
                span.set_attribute("output_tokens", usage.output_tokens)

            return response

    except Exception as e:
        error_msg = str(e)
        raise
    finally:
        duration_ms = (time.time() - start_time) * 1000
        logger.debug(
            "Anthropic call traced",
            model=model,
            duration_ms=duration_ms,
            error=error_msg,
        )


def _trace_anthropic_call_sync(
    original_fn: Callable[..., Any],
    tracer: "Tracer",
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Trace a sync Anthropic API call."""
    model = kwargs.get("model", "unknown")
    messages = kwargs.get("messages", [])

    prompt = _extract_prompt(messages)
    start_time = time.time()
    error_msg = None

    try:
        with tracer.span(f"anthropic:{model}", span_type=SpanType.llm_call) as span:
            span.set_attribute("model", model)
            span.set_attribute("provider", "anthropic")
            span.set_attribute("max_tokens", kwargs.get("max_tokens"))
            span.set_attribute("temperature", kwargs.get("temperature"))

            response = original_fn(*args, **kwargs)

            content = _extract_response_content(response)
            usage = getattr(response, "usage", None)

            span.set_attribute("response", content[:1000] if content else None)
            if usage:
                span.set_attribute("input_tokens", usage.input_tokens)
                span.set_attribute("output_tokens", usage.output_tokens)

            return response

    except Exception as e:
        error_msg = str(e)
        raise
    finally:
        duration_ms = (time.time() - start_time) * 1000
        logger.debug(
            "Anthropic call traced",
            model=model,
            duration_ms=duration_ms,
            error=error_msg,
        )


def _extract_prompt(messages: list[dict[str, Any]]) -> str:
    """Extract prompt text from messages."""
    parts = []
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if isinstance(content, list):
            # Handle content blocks
            text_parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
            content = " ".join(text_parts)
        parts.append(f"{role}: {content}")
    return "\n".join(parts)


def _extract_response_content(response: Any) -> str:
    """Extract text content from response."""
    if hasattr(response, "content") and response.content:
        parts = []
        for block in response.content:
            if hasattr(block, "text"):
                parts.append(block.text)
            elif hasattr(block, "type") and block.type == "tool_use":
                parts.append(f"[tool_use: {getattr(block, 'name', 'unknown')}]")
        return " ".join(parts)
    return ""
