"""Auto-instrumentation for OpenAI SDK."""

from __future__ import annotations

import functools
import time
from typing import TYPE_CHECKING, Any, Callable

from trustmodel.core.logging import get_logger
from trustmodel.models.trace import SpanType

if TYPE_CHECKING:
    from trustmodel.connect.tracer import Tracer

logger = get_logger(__name__)


def patch_openai(tracer: "Tracer") -> None:
    """Patch OpenAI SDK to automatically trace API calls."""
    try:
        import openai
    except ImportError:
        logger.debug("OpenAI SDK not installed, skipping patch")
        return

    # Patch synchronous client
    if hasattr(openai, "OpenAI"):
        _patch_sync_client(openai.OpenAI, tracer)

    # Patch async client
    if hasattr(openai, "AsyncOpenAI"):
        _patch_async_client(openai.AsyncOpenAI, tracer)

    logger.info("OpenAI SDK patched for tracing")


def _patch_sync_client(client_class: type, tracer: "Tracer") -> None:
    """Patch synchronous OpenAI client."""
    original_init = client_class.__init__

    @functools.wraps(original_init)
    def patched_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        _patch_chat_completions(self.chat.completions, tracer, is_async=False)

    client_class.__init__ = patched_init


def _patch_async_client(client_class: type, tracer: "Tracer") -> None:
    """Patch async OpenAI client."""
    original_init = client_class.__init__

    @functools.wraps(original_init)
    def patched_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        _patch_chat_completions(self.chat.completions, tracer, is_async=True)

    client_class.__init__ = patched_init


def _patch_chat_completions(completions: Any, tracer: "Tracer", is_async: bool) -> None:
    """Patch the chat completions resource."""
    original_create = completions.create

    if is_async:
        @functools.wraps(original_create)
        async def traced_create(*args: Any, **kwargs: Any) -> Any:
            return await _trace_openai_call_async(original_create, tracer, *args, **kwargs)
        completions.create = traced_create
    else:
        @functools.wraps(original_create)
        def traced_create(*args: Any, **kwargs: Any) -> Any:
            return _trace_openai_call_sync(original_create, tracer, *args, **kwargs)
        completions.create = traced_create


async def _trace_openai_call_async(
    original_fn: Callable[..., Any],
    tracer: "Tracer",
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Trace an async OpenAI API call."""
    model = kwargs.get("model", "unknown")
    messages = kwargs.get("messages", [])

    prompt = _extract_prompt(messages)
    start_time = time.time()
    error_msg = None

    try:
        with tracer.span(f"openai:{model}", span_type=SpanType.llm_call) as span:
            span.set_attribute("model", model)
            span.set_attribute("provider", "openai")
            span.set_attribute("max_tokens", kwargs.get("max_tokens"))
            span.set_attribute("temperature", kwargs.get("temperature"))
            span.set_attribute("prompt", prompt[:2000])

            response = await original_fn(*args, **kwargs)

            # Extract response data
            content = _extract_response_content(response)
            usage = getattr(response, "usage", None)

            span.set_attribute("response", content[:1000] if content else None)
            if usage:
                span.set_attribute("input_tokens", usage.prompt_tokens)
                span.set_attribute("output_tokens", usage.completion_tokens)
                span.set_attribute("total_tokens", usage.total_tokens)

            # Check for function/tool calls
            if response.choices and response.choices[0].message.tool_calls:
                tool_calls = []
                for tc in response.choices[0].message.tool_calls:
                    tool_calls.append({
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    })
                span.set_attribute("tool_calls", tool_calls)

            return response

    except Exception as e:
        error_msg = str(e)
        raise
    finally:
        duration_ms = (time.time() - start_time) * 1000
        logger.debug(
            "OpenAI call traced",
            model=model,
            duration_ms=duration_ms,
            error=error_msg,
        )


def _trace_openai_call_sync(
    original_fn: Callable[..., Any],
    tracer: "Tracer",
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Trace a sync OpenAI API call."""
    model = kwargs.get("model", "unknown")
    messages = kwargs.get("messages", [])

    prompt = _extract_prompt(messages)
    start_time = time.time()
    error_msg = None

    try:
        with tracer.span(f"openai:{model}", span_type=SpanType.llm_call) as span:
            span.set_attribute("model", model)
            span.set_attribute("provider", "openai")
            span.set_attribute("max_tokens", kwargs.get("max_tokens"))
            span.set_attribute("temperature", kwargs.get("temperature"))
            span.set_attribute("prompt", prompt[:2000])

            response = original_fn(*args, **kwargs)

            content = _extract_response_content(response)
            usage = getattr(response, "usage", None)

            span.set_attribute("response", content[:1000] if content else None)
            if usage:
                span.set_attribute("input_tokens", usage.prompt_tokens)
                span.set_attribute("output_tokens", usage.completion_tokens)
                span.set_attribute("total_tokens", usage.total_tokens)

            if response.choices and response.choices[0].message.tool_calls:
                tool_calls = []
                for tc in response.choices[0].message.tool_calls:
                    tool_calls.append({
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    })
                span.set_attribute("tool_calls", tool_calls)

            return response

    except Exception as e:
        error_msg = str(e)
        raise
    finally:
        duration_ms = (time.time() - start_time) * 1000
        logger.debug(
            "OpenAI call traced",
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
            text_parts = []
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
            content = " ".join(text_parts)
        parts.append(f"{role}: {content}")
    return "\n".join(parts)


def _extract_response_content(response: Any) -> str:
    """Extract text content from response."""
    if hasattr(response, "choices") and response.choices:
        choice = response.choices[0]
        if hasattr(choice, "message") and hasattr(choice.message, "content"):
            return choice.message.content or ""
    return ""
