"""Tracer for collecting spans and traces."""

from __future__ import annotations

import contextvars
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Generator, Optional
from uuid import UUID, uuid4

from trustmodel.connect.exporters import BatchTraceExporter
from trustmodel.core.logging import get_logger
from trustmodel.models.trace import Span, SpanCreate, SpanStatus, SpanType, Trace, TraceCreate

logger = get_logger(__name__)

# Context variables for trace context propagation
_current_trace_id: contextvars.ContextVar[Optional[UUID]] = contextvars.ContextVar(
    "_current_trace_id", default=None
)
_current_span_id: contextvars.ContextVar[Optional[UUID]] = contextvars.ContextVar(
    "_current_span_id", default=None
)
_current_tracer: contextvars.ContextVar[Optional["Tracer"]] = contextvars.ContextVar(
    "_current_tracer", default=None
)


class SpanContext:
    """Context manager for a span."""

    def __init__(
        self,
        tracer: "Tracer",
        span: SpanCreate,
        trace_id: UUID,
    ) -> None:
        self.tracer = tracer
        self.span = span
        self.trace_id = trace_id
        self._token_trace: Optional[contextvars.Token[Optional[UUID]]] = None
        self._token_span: Optional[contextvars.Token[Optional[UUID]]] = None

    def __enter__(self) -> "SpanContext":
        self._token_trace = _current_trace_id.set(self.trace_id)
        self._token_span = _current_span_id.set(self.span.span_id)
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Any,
    ) -> None:
        # End the span
        self.span.ended_at = datetime.now(timezone.utc)

        if exc_type is not None:
            self.span.status = SpanStatus.error
            self.span.error_type = exc_type.__name__
            self.span.error_message = str(exc_val)

        # Record the span
        self.tracer._record_span(self.trace_id, self.span)

        # Restore context
        if self._token_trace:
            _current_trace_id.reset(self._token_trace)
        if self._token_span:
            _current_span_id.reset(self._token_span)

    def set_attribute(self, key: str, value: Any) -> None:
        """Set an attribute on the span."""
        self.span.attributes[key] = value

    def set_status(self, status: SpanStatus, message: Optional[str] = None) -> None:
        """Set the span status."""
        self.span.status = status
        if message and status == SpanStatus.error:
            self.span.error_message = message

    def add_event(self, name: str, attributes: Optional[dict[str, Any]] = None) -> None:
        """Add an event to the span."""
        events = self.span.attributes.get("events", [])
        events.append({
            "name": name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "attributes": attributes or {},
        })
        self.span.attributes["events"] = events


class Tracer:
    """Tracer for collecting spans and building traces."""

    def __init__(
        self,
        agent_id: UUID,
        agent_name: str,
        exporter: BatchTraceExporter,
        sample_rate: float = 1.0,
    ) -> None:
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.exporter = exporter
        self.sample_rate = sample_rate
        self._traces: dict[UUID, TraceCreate] = {}
        self._active = True

        # Set as current tracer
        _current_tracer.set(self)

    def start_trace(
        self,
        session_id: Optional[UUID] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> UUID:
        """Start a new trace."""
        trace_id = uuid4()
        trace = TraceCreate(
            trace_id=trace_id,
            session_id=session_id,
            started_at=datetime.now(timezone.utc),
            metadata=metadata or {},
            spans=[],
        )
        self._traces[trace_id] = trace
        _current_trace_id.set(trace_id)
        logger.debug("Started trace", trace_id=str(trace_id))
        return trace_id

    def end_trace(self, trace_id: Optional[UUID] = None) -> None:
        """End a trace and export it."""
        trace_id = trace_id or _current_trace_id.get()
        if not trace_id or trace_id not in self._traces:
            return

        trace = self._traces.pop(trace_id)
        trace.ended_at = datetime.now(timezone.utc)

        # Export trace
        if self._active:
            self.exporter.add_trace(trace)

        logger.debug(
            "Ended trace",
            trace_id=str(trace_id),
            span_count=len(trace.spans),
        )

    @contextmanager
    def span(
        self,
        name: str,
        span_type: SpanType = SpanType.custom,
        attributes: Optional[dict[str, Any]] = None,
    ) -> Generator[SpanContext, None, None]:
        """Create a span within the current trace."""
        # Get or create trace
        trace_id = _current_trace_id.get()
        if not trace_id:
            trace_id = self.start_trace()

        # Get parent span
        parent_span_id = _current_span_id.get()

        # Create span
        span = SpanCreate(
            span_id=uuid4(),
            parent_span_id=parent_span_id,
            span_type=span_type,
            name=name,
            started_at=datetime.now(timezone.utc),
            attributes=attributes or {},
        )

        ctx = SpanContext(self, span, trace_id)
        try:
            yield ctx
        finally:
            pass  # Cleanup happens in SpanContext.__exit__

    def llm_span(
        self,
        name: str,
        model: Optional[str] = None,
        attributes: Optional[dict[str, Any]] = None,
    ) -> SpanContext:
        """Create an LLM call span."""
        attrs = attributes or {}
        if model:
            attrs["model"] = model
        return self.span(name, span_type=SpanType.llm_call, attributes=attrs).__enter__()

    def tool_span(
        self,
        tool_name: str,
        tool_input: Optional[dict[str, Any]] = None,
        attributes: Optional[dict[str, Any]] = None,
    ) -> SpanContext:
        """Create a tool call span."""
        attrs = attributes or {}
        attrs["tool_name"] = tool_name
        if tool_input:
            attrs["tool_input"] = tool_input
        return self.span(
            f"tool:{tool_name}",
            span_type=SpanType.tool_call,
            attributes=attrs,
        ).__enter__()

    def _record_span(self, trace_id: UUID, span: SpanCreate) -> None:
        """Record a completed span."""
        if trace_id in self._traces:
            self._traces[trace_id].spans.append(span)

    def record_llm_call(
        self,
        model: str,
        prompt: str,
        response: str,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        duration_ms: Optional[float] = None,
        attributes: Optional[dict[str, Any]] = None,
    ) -> None:
        """Record a completed LLM call as a span."""
        trace_id = _current_trace_id.get()
        if not trace_id:
            trace_id = self.start_trace()

        now = datetime.now(timezone.utc)
        started_at = now
        if duration_ms:
            from datetime import timedelta
            started_at = now - timedelta(milliseconds=duration_ms)

        span = SpanCreate(
            span_id=uuid4(),
            parent_span_id=_current_span_id.get(),
            span_type=SpanType.llm_call,
            name=f"llm:{model}",
            started_at=started_at,
            ended_at=now,
            model=model,
            prompt=prompt,
            response=response,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            attributes=attributes or {},
        )

        self._record_span(trace_id, span)

    def record_tool_call(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        tool_output: Any,
        success: bool = True,
        error: Optional[str] = None,
        duration_ms: Optional[float] = None,
    ) -> None:
        """Record a completed tool call as a span."""
        trace_id = _current_trace_id.get()
        if not trace_id:
            trace_id = self.start_trace()

        now = datetime.now(timezone.utc)
        started_at = now
        if duration_ms:
            from datetime import timedelta
            started_at = now - timedelta(milliseconds=duration_ms)

        span = SpanCreate(
            span_id=uuid4(),
            parent_span_id=_current_span_id.get(),
            span_type=SpanType.tool_call,
            name=f"tool:{tool_name}",
            started_at=started_at,
            ended_at=now,
            status=SpanStatus.ok if success else SpanStatus.error,
            tool_name=tool_name,
            tool_input=tool_input,
            tool_output=tool_output,
            error_message=error,
        )

        self._record_span(trace_id, span)

    async def flush(self) -> None:
        """Flush pending traces to the server."""
        await self.exporter.flush()

    async def shutdown(self) -> None:
        """Shutdown the tracer."""
        self._active = False
        await self.exporter.shutdown()


@lru_cache()
def get_tracer() -> Optional[Tracer]:
    """Get the current tracer."""
    return _current_tracer.get()


def get_current_trace_id() -> Optional[UUID]:
    """Get the current trace ID."""
    return _current_trace_id.get()


def get_current_span_id() -> Optional[UUID]:
    """Get the current span ID."""
    return _current_span_id.get()
