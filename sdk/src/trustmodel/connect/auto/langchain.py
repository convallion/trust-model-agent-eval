"""Auto-instrumentation for LangChain."""

from __future__ import annotations

import functools
import time
from typing import TYPE_CHECKING, Any, Callable

from trustmodel.core.logging import get_logger
from trustmodel.models.trace import SpanType

if TYPE_CHECKING:
    from trustmodel.connect.tracer import Tracer

logger = get_logger(__name__)


def patch_langchain(tracer: "Tracer") -> None:
    """Patch LangChain to automatically trace calls."""
    try:
        from langchain_core.language_models import BaseChatModel, BaseLLM
        from langchain_core.tools import BaseTool
    except ImportError:
        try:
            from langchain.chat_models.base import BaseChatModel
            from langchain.llms.base import BaseLLM
            from langchain.tools.base import BaseTool
        except ImportError:
            logger.debug("LangChain not installed, skipping patch")
            return

    # Patch chat models
    _patch_chat_model(BaseChatModel, tracer)

    # Patch LLMs
    _patch_llm(BaseLLM, tracer)

    # Patch tools
    _patch_tool(BaseTool, tracer)

    logger.info("LangChain patched for tracing")


def _patch_chat_model(chat_model_class: type, tracer: "Tracer") -> None:
    """Patch BaseChatModel for tracing."""
    original_invoke = getattr(chat_model_class, "invoke", None)
    original_ainvoke = getattr(chat_model_class, "ainvoke", None)

    if original_invoke:
        @functools.wraps(original_invoke)
        def traced_invoke(self: Any, *args: Any, **kwargs: Any) -> Any:
            return _trace_chat_model_sync(self, original_invoke, tracer, *args, **kwargs)
        chat_model_class.invoke = traced_invoke

    if original_ainvoke:
        @functools.wraps(original_ainvoke)
        async def traced_ainvoke(self: Any, *args: Any, **kwargs: Any) -> Any:
            return await _trace_chat_model_async(self, original_ainvoke, tracer, *args, **kwargs)
        chat_model_class.ainvoke = traced_ainvoke


def _patch_llm(llm_class: type, tracer: "Tracer") -> None:
    """Patch BaseLLM for tracing."""
    original_invoke = getattr(llm_class, "invoke", None)
    original_ainvoke = getattr(llm_class, "ainvoke", None)

    if original_invoke:
        @functools.wraps(original_invoke)
        def traced_invoke(self: Any, *args: Any, **kwargs: Any) -> Any:
            return _trace_llm_sync(self, original_invoke, tracer, *args, **kwargs)
        llm_class.invoke = traced_invoke

    if original_ainvoke:
        @functools.wraps(original_ainvoke)
        async def traced_ainvoke(self: Any, *args: Any, **kwargs: Any) -> Any:
            return await _trace_llm_async(self, original_ainvoke, tracer, *args, **kwargs)
        llm_class.ainvoke = traced_ainvoke


def _patch_tool(tool_class: type, tracer: "Tracer") -> None:
    """Patch BaseTool for tracing."""
    original_invoke = getattr(tool_class, "invoke", None)
    original_ainvoke = getattr(tool_class, "ainvoke", None)

    if original_invoke:
        @functools.wraps(original_invoke)
        def traced_invoke(self: Any, *args: Any, **kwargs: Any) -> Any:
            return _trace_tool_sync(self, original_invoke, tracer, *args, **kwargs)
        tool_class.invoke = traced_invoke

    if original_ainvoke:
        @functools.wraps(original_ainvoke)
        async def traced_ainvoke(self: Any, *args: Any, **kwargs: Any) -> Any:
            return await _trace_tool_async(self, original_ainvoke, tracer, *args, **kwargs)
        tool_class.ainvoke = traced_ainvoke


def _trace_chat_model_sync(
    model: Any,
    original_fn: Callable[..., Any],
    tracer: "Tracer",
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Trace a sync chat model call."""
    model_name = getattr(model, "model_name", None) or getattr(model, "model", "unknown")
    start_time = time.time()

    try:
        with tracer.span(f"langchain:chat:{model_name}", span_type=SpanType.llm_call) as span:
            span.set_attribute("model", model_name)
            span.set_attribute("provider", "langchain")
            span.set_attribute("model_class", model.__class__.__name__)

            # Extract input
            if args:
                input_data = _serialize_messages(args[0])
                span.set_attribute("input", str(input_data)[:2000])

            response = original_fn(model, *args, **kwargs)

            # Extract output
            output = _serialize_response(response)
            span.set_attribute("output", str(output)[:1000])

            return response

    finally:
        duration_ms = (time.time() - start_time) * 1000
        logger.debug("LangChain chat model traced", model=model_name, duration_ms=duration_ms)


async def _trace_chat_model_async(
    model: Any,
    original_fn: Callable[..., Any],
    tracer: "Tracer",
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Trace an async chat model call."""
    model_name = getattr(model, "model_name", None) or getattr(model, "model", "unknown")
    start_time = time.time()

    try:
        with tracer.span(f"langchain:chat:{model_name}", span_type=SpanType.llm_call) as span:
            span.set_attribute("model", model_name)
            span.set_attribute("provider", "langchain")
            span.set_attribute("model_class", model.__class__.__name__)

            if args:
                input_data = _serialize_messages(args[0])
                span.set_attribute("input", str(input_data)[:2000])

            response = await original_fn(model, *args, **kwargs)

            output = _serialize_response(response)
            span.set_attribute("output", str(output)[:1000])

            return response

    finally:
        duration_ms = (time.time() - start_time) * 1000
        logger.debug("LangChain chat model traced", model=model_name, duration_ms=duration_ms)


def _trace_llm_sync(
    model: Any,
    original_fn: Callable[..., Any],
    tracer: "Tracer",
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Trace a sync LLM call."""
    model_name = getattr(model, "model_name", None) or getattr(model, "model", "unknown")
    start_time = time.time()

    try:
        with tracer.span(f"langchain:llm:{model_name}", span_type=SpanType.llm_call) as span:
            span.set_attribute("model", model_name)
            span.set_attribute("provider", "langchain")

            if args:
                span.set_attribute("prompt", str(args[0])[:2000])

            response = original_fn(model, *args, **kwargs)
            span.set_attribute("response", str(response)[:1000])

            return response

    finally:
        duration_ms = (time.time() - start_time) * 1000
        logger.debug("LangChain LLM traced", model=model_name, duration_ms=duration_ms)


async def _trace_llm_async(
    model: Any,
    original_fn: Callable[..., Any],
    tracer: "Tracer",
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Trace an async LLM call."""
    model_name = getattr(model, "model_name", None) or getattr(model, "model", "unknown")
    start_time = time.time()

    try:
        with tracer.span(f"langchain:llm:{model_name}", span_type=SpanType.llm_call) as span:
            span.set_attribute("model", model_name)
            span.set_attribute("provider", "langchain")

            if args:
                span.set_attribute("prompt", str(args[0])[:2000])

            response = await original_fn(model, *args, **kwargs)
            span.set_attribute("response", str(response)[:1000])

            return response

    finally:
        duration_ms = (time.time() - start_time) * 1000
        logger.debug("LangChain LLM traced", model=model_name, duration_ms=duration_ms)


def _trace_tool_sync(
    tool: Any,
    original_fn: Callable[..., Any],
    tracer: "Tracer",
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Trace a sync tool call."""
    tool_name = getattr(tool, "name", tool.__class__.__name__)
    start_time = time.time()

    try:
        with tracer.span(f"langchain:tool:{tool_name}", span_type=SpanType.tool_call) as span:
            span.set_attribute("tool_name", tool_name)
            span.set_attribute("tool_description", getattr(tool, "description", None))

            if args:
                span.set_attribute("tool_input", str(args[0])[:1000])

            response = original_fn(tool, *args, **kwargs)
            span.set_attribute("tool_output", str(response)[:1000])

            return response

    finally:
        duration_ms = (time.time() - start_time) * 1000
        logger.debug("LangChain tool traced", tool=tool_name, duration_ms=duration_ms)


async def _trace_tool_async(
    tool: Any,
    original_fn: Callable[..., Any],
    tracer: "Tracer",
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Trace an async tool call."""
    tool_name = getattr(tool, "name", tool.__class__.__name__)
    start_time = time.time()

    try:
        with tracer.span(f"langchain:tool:{tool_name}", span_type=SpanType.tool_call) as span:
            span.set_attribute("tool_name", tool_name)
            span.set_attribute("tool_description", getattr(tool, "description", None))

            if args:
                span.set_attribute("tool_input", str(args[0])[:1000])

            response = await original_fn(tool, *args, **kwargs)
            span.set_attribute("tool_output", str(response)[:1000])

            return response

    finally:
        duration_ms = (time.time() - start_time) * 1000
        logger.debug("LangChain tool traced", tool=tool_name, duration_ms=duration_ms)


def _serialize_messages(messages: Any) -> list[dict[str, Any]]:
    """Serialize LangChain messages to dicts."""
    if isinstance(messages, list):
        result = []
        for msg in messages:
            if hasattr(msg, "type") and hasattr(msg, "content"):
                result.append({"type": msg.type, "content": str(msg.content)[:500]})
            else:
                result.append({"content": str(msg)[:500]})
        return result
    return [{"content": str(messages)[:500]}]


def _serialize_response(response: Any) -> dict[str, Any]:
    """Serialize LangChain response to dict."""
    if hasattr(response, "content"):
        return {"content": str(response.content)[:1000]}
    return {"content": str(response)[:1000]}
