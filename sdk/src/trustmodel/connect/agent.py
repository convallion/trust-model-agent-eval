"""Base TracedAgent class for building instrumented agents."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional
from uuid import UUID

from trustmodel.connect.tracer import Tracer, get_tracer
from trustmodel.core.logging import get_logger
from trustmodel.models.trace import SpanType

logger = get_logger(__name__)


class TracedAgent(ABC):
    """
    Base class for building instrumented AI agents.

    Extend this class to create agents with automatic tracing.
    All method calls are automatically traced when using the
    provided decorators or context managers.

    Example:
        class MyAgent(TracedAgent):
            async def run(self, task: str) -> str:
                with self.span("process_task"):
                    # Your agent logic here
                    result = await self.call_llm(task)
                    return result

            async def call_llm(self, prompt: str) -> str:
                with self.llm_span("claude-3-opus"):
                    response = await anthropic.messages.create(...)
                    return response.content[0].text
    """

    def __init__(
        self,
        name: str,
        tracer: Optional[Tracer] = None,
    ) -> None:
        self.name = name
        self._tracer = tracer or get_tracer()
        self._session_id: Optional[UUID] = None

    @property
    def tracer(self) -> Optional[Tracer]:
        """Get the tracer instance."""
        return self._tracer

    @property
    def agent_id(self) -> Optional[UUID]:
        """Get the agent ID if instrumented."""
        if self._tracer:
            return self._tracer.agent_id
        return None

    def set_session(self, session_id: UUID) -> None:
        """Set the current session ID for trace correlation."""
        self._session_id = session_id

    def start_trace(self, metadata: Optional[dict[str, Any]] = None) -> Optional[UUID]:
        """Start a new trace for this agent's execution."""
        if not self._tracer:
            return None

        trace_meta = metadata or {}
        trace_meta["agent_name"] = self.name

        return self._tracer.start_trace(
            session_id=self._session_id,
            metadata=trace_meta,
        )

    def end_trace(self, trace_id: Optional[UUID] = None) -> None:
        """End the current or specified trace."""
        if self._tracer:
            self._tracer.end_trace(trace_id)

    def span(self, name: str, span_type: SpanType = SpanType.agent_action, **attributes: Any):
        """Create a span context manager."""
        if not self._tracer:
            # Return a no-op context manager
            from contextlib import nullcontext
            return nullcontext()

        return self._tracer.span(name, span_type=span_type, attributes=attributes)

    def llm_span(self, model: str, **attributes: Any):
        """Create an LLM call span context manager."""
        if not self._tracer:
            from contextlib import nullcontext
            return nullcontext()

        attrs = {"model": model, **attributes}
        return self._tracer.span(f"llm:{model}", span_type=SpanType.llm_call, attributes=attrs)

    def tool_span(self, tool_name: str, **attributes: Any):
        """Create a tool call span context manager."""
        if not self._tracer:
            from contextlib import nullcontext
            return nullcontext()

        attrs = {"tool_name": tool_name, **attributes}
        return self._tracer.span(
            f"tool:{tool_name}",
            span_type=SpanType.tool_call,
            attributes=attrs,
        )

    def record_llm_call(
        self,
        model: str,
        prompt: str,
        response: str,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        duration_ms: Optional[float] = None,
        **attributes: Any,
    ) -> None:
        """Record a completed LLM call."""
        if self._tracer:
            self._tracer.record_llm_call(
                model=model,
                prompt=prompt,
                response=response,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                duration_ms=duration_ms,
                attributes=attributes,
            )

    def record_tool_call(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        tool_output: Any,
        success: bool = True,
        error: Optional[str] = None,
        duration_ms: Optional[float] = None,
    ) -> None:
        """Record a completed tool call."""
        if self._tracer:
            self._tracer.record_tool_call(
                tool_name=tool_name,
                tool_input=tool_input,
                tool_output=tool_output,
                success=success,
                error=error,
                duration_ms=duration_ms,
            )

    @abstractmethod
    async def run(self, task: str, **kwargs: Any) -> Any:
        """
        Execute the agent's main task.

        Override this method to implement your agent's logic.
        Use self.span(), self.llm_span(), etc. for automatic tracing.

        Args:
            task: The task description or prompt
            **kwargs: Additional task parameters

        Returns:
            The result of the agent's execution
        """
        pass

    async def __call__(self, task: str, **kwargs: Any) -> Any:
        """Execute the agent (calls run with tracing)."""
        trace_id = self.start_trace(metadata={"task": task[:100]})
        try:
            with self.span("agent_run", task=task[:100]):
                result = await self.run(task, **kwargs)
                return result
        finally:
            self.end_trace(trace_id)


class SimpleAgent(TracedAgent):
    """
    Simple agent implementation for quick prototyping.

    Use this when you don't need a custom agent class but want
    tracing capabilities.

    Example:
        agent = SimpleAgent("my-agent")

        async with agent.traced_execution("process task"):
            # Your code here
            pass
    """

    def __init__(
        self,
        name: str,
        tracer: Optional[Tracer] = None,
    ) -> None:
        super().__init__(name, tracer)
        self._handler: Optional[Any] = None

    def set_handler(self, handler: Any) -> None:
        """Set the handler function for run()."""
        self._handler = handler

    async def run(self, task: str, **kwargs: Any) -> Any:
        """Execute the configured handler or raise NotImplementedError."""
        if self._handler:
            if asyncio.iscoroutinefunction(self._handler):
                return await self._handler(task, **kwargs)
            return self._handler(task, **kwargs)
        raise NotImplementedError("No handler set. Use set_handler() or extend TracedAgent.")

    def traced_execution(self, name: str, **attributes: Any):
        """Context manager for traced execution blocks."""
        return self.span(name, **attributes)


# Import asyncio for SimpleAgent
import asyncio
