"""Metrics collection and analysis from agent traces."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

import structlog

logger = structlog.get_logger()


@dataclass
class ToolCallMetrics:
    """Metrics for a single tool call."""

    tool_name: str
    duration_ms: int
    success: bool
    error: Optional[str] = None
    parameters: dict[str, Any] = field(default_factory=dict)
    result_size: Optional[int] = None


@dataclass
class LLMCallMetrics:
    """Metrics for a single LLM call."""

    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    duration_ms: int
    success: bool
    error: Optional[str] = None


@dataclass
class StepMetrics:
    """Metrics for a single execution step."""

    step_number: int
    step_type: str  # "llm", "tool", "reasoning"
    duration_ms: int
    tokens_used: int = 0
    tool_calls: list[ToolCallMetrics] = field(default_factory=list)
    llm_calls: list[LLMCallMetrics] = field(default_factory=list)


@dataclass
class TraceMetrics:
    """Aggregated metrics from an agent execution trace."""

    trace_id: UUID
    agent_id: UUID
    task_id: str

    # Timing metrics
    total_duration_ms: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Token metrics
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0

    # Step metrics
    total_steps: int = 0
    steps: list[StepMetrics] = field(default_factory=list)

    # Tool metrics
    total_tool_calls: int = 0
    successful_tool_calls: int = 0
    failed_tool_calls: int = 0
    unique_tools_used: set[str] = field(default_factory=set)

    # LLM metrics
    total_llm_calls: int = 0
    models_used: set[str] = field(default_factory=set)

    # Success metrics
    task_completed: bool = False
    error_message: Optional[str] = None

    def calculate_efficiency_score(self) -> float:
        """
        Calculate efficiency score based on metrics.

        Returns a score from 0-100 based on:
        - Token efficiency
        - Step efficiency
        - Tool usage efficiency
        """
        scores = []

        # Token efficiency (lower is better, up to reasonable threshold)
        if self.total_tokens > 0:
            token_score = max(0, 100 - (self.total_tokens / 100))
            scores.append(min(100, token_score))

        # Step efficiency (fewer steps for same result is better)
        if self.total_steps > 0:
            step_score = max(0, 100 - (self.total_steps * 5))
            scores.append(min(100, step_score))

        # Tool call efficiency
        if self.total_tool_calls > 0:
            success_rate = self.successful_tool_calls / self.total_tool_calls
            scores.append(success_rate * 100)

        # Time efficiency (under 60 seconds is good)
        if self.total_duration_ms > 0:
            time_seconds = self.total_duration_ms / 1000
            time_score = max(0, 100 - (time_seconds / 60 * 50))
            scores.append(min(100, time_score))

        return sum(scores) / len(scores) if scores else 50.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "trace_id": str(self.trace_id),
            "agent_id": str(self.agent_id),
            "task_id": self.task_id,
            "total_duration_ms": self.total_duration_ms,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "total_tokens": self.total_tokens,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_steps": self.total_steps,
            "total_tool_calls": self.total_tool_calls,
            "successful_tool_calls": self.successful_tool_calls,
            "failed_tool_calls": self.failed_tool_calls,
            "unique_tools_used": list(self.unique_tools_used),
            "total_llm_calls": self.total_llm_calls,
            "models_used": list(self.models_used),
            "task_completed": self.task_completed,
            "error_message": self.error_message,
            "efficiency_score": self.calculate_efficiency_score(),
        }


class TraceAnalyzer:
    """Analyzes agent execution traces to extract metrics."""

    def __init__(self) -> None:
        """Initialize the trace analyzer."""
        pass

    def analyze_trace(self, trace_data: dict[str, Any]) -> TraceMetrics:
        """
        Analyze a trace and extract metrics.

        Args:
            trace_data: Raw trace data from agent execution

        Returns:
            TraceMetrics with aggregated metrics
        """
        from uuid import uuid4

        metrics = TraceMetrics(
            trace_id=UUID(trace_data.get("id", str(uuid4()))),
            agent_id=UUID(trace_data.get("agent_id", str(uuid4()))),
            task_id=trace_data.get("task_id", "unknown"),
        )

        # Extract timing
        if "started_at" in trace_data:
            metrics.started_at = self._parse_timestamp(trace_data["started_at"])
        if "completed_at" in trace_data:
            metrics.completed_at = self._parse_timestamp(trace_data["completed_at"])
        if metrics.started_at and metrics.completed_at:
            metrics.total_duration_ms = int(
                (metrics.completed_at - metrics.started_at).total_seconds() * 1000
            )
        elif "duration_ms" in trace_data:
            metrics.total_duration_ms = trace_data["duration_ms"]

        # Extract steps/spans
        spans = trace_data.get("spans", [])
        for i, span in enumerate(spans):
            step = self._analyze_span(span, i)
            metrics.steps.append(step)
            metrics.total_steps += 1

            # Aggregate token counts
            for llm_call in step.llm_calls:
                metrics.total_tokens += llm_call.total_tokens
                metrics.prompt_tokens += llm_call.prompt_tokens
                metrics.completion_tokens += llm_call.completion_tokens
                metrics.total_llm_calls += 1
                metrics.models_used.add(llm_call.model)

            # Aggregate tool call counts
            for tool_call in step.tool_calls:
                metrics.total_tool_calls += 1
                if tool_call.success:
                    metrics.successful_tool_calls += 1
                else:
                    metrics.failed_tool_calls += 1
                metrics.unique_tools_used.add(tool_call.tool_name)

        # Extract completion status
        metrics.task_completed = trace_data.get("status") == "completed"
        metrics.error_message = trace_data.get("error")

        # Direct token count if available
        if "total_tokens" in trace_data:
            metrics.total_tokens = trace_data["total_tokens"]
        if "prompt_tokens" in trace_data:
            metrics.prompt_tokens = trace_data["prompt_tokens"]
        if "completion_tokens" in trace_data:
            metrics.completion_tokens = trace_data["completion_tokens"]

        return metrics

    def _analyze_span(self, span: dict[str, Any], index: int) -> StepMetrics:
        """Analyze a single span/step."""
        step = StepMetrics(
            step_number=index,
            step_type=span.get("type", "unknown"),
            duration_ms=span.get("duration_ms", 0),
        )

        # Extract LLM calls
        llm_calls = span.get("llm_calls", [])
        for llm_call in llm_calls:
            step.llm_calls.append(
                LLMCallMetrics(
                    model=llm_call.get("model", "unknown"),
                    prompt_tokens=llm_call.get("prompt_tokens", 0),
                    completion_tokens=llm_call.get("completion_tokens", 0),
                    total_tokens=llm_call.get("total_tokens", 0),
                    duration_ms=llm_call.get("duration_ms", 0),
                    success=llm_call.get("success", True),
                    error=llm_call.get("error"),
                )
            )
            step.tokens_used += llm_call.get("total_tokens", 0)

        # Extract tool calls
        tool_calls = span.get("tool_calls", [])
        for tool_call in tool_calls:
            step.tool_calls.append(
                ToolCallMetrics(
                    tool_name=tool_call.get("tool_name", "unknown"),
                    duration_ms=tool_call.get("duration_ms", 0),
                    success=tool_call.get("success", True),
                    error=tool_call.get("error"),
                    parameters=tool_call.get("parameters", {}),
                    result_size=tool_call.get("result_size"),
                )
            )

        return step

    def _parse_timestamp(self, value: Any) -> datetime:
        """Parse a timestamp value."""
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, tz=timezone.utc)
        return datetime.now(timezone.utc)

    def compare_traces(
        self,
        traces: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Compare multiple traces for consistency analysis.

        Args:
            traces: List of trace data from multiple runs

        Returns:
            Comparison metrics and consistency scores
        """
        if not traces:
            return {"error": "No traces to compare"}

        metrics_list = [self.analyze_trace(t) for t in traces]

        # Calculate variance in key metrics
        durations = [m.total_duration_ms for m in metrics_list]
        tokens = [m.total_tokens for m in metrics_list]
        steps = [m.total_steps for m in metrics_list]

        return {
            "trace_count": len(traces),
            "all_completed": all(m.task_completed for m in metrics_list),
            "completion_rate": sum(1 for m in metrics_list if m.task_completed) / len(metrics_list),
            "duration": {
                "min": min(durations),
                "max": max(durations),
                "mean": sum(durations) / len(durations),
                "variance": self._variance(durations),
            },
            "tokens": {
                "min": min(tokens),
                "max": max(tokens),
                "mean": sum(tokens) / len(tokens),
                "variance": self._variance(tokens),
            },
            "steps": {
                "min": min(steps),
                "max": max(steps),
                "mean": sum(steps) / len(steps),
                "variance": self._variance(steps),
            },
            "consistency_score": self._calculate_consistency_score(metrics_list),
        }

    def _variance(self, values: list[float]) -> float:
        """Calculate variance of a list of values."""
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        return sum((x - mean) ** 2 for x in values) / len(values)

    def _calculate_consistency_score(self, metrics_list: list[TraceMetrics]) -> float:
        """
        Calculate consistency score across multiple runs.

        Returns 0-100 where 100 is perfectly consistent.
        """
        if len(metrics_list) < 2:
            return 100.0

        # All should complete or all should fail
        completion_states = [m.task_completed for m in metrics_list]
        completion_consistency = 1.0 if len(set(completion_states)) == 1 else 0.5

        # Check step count consistency
        steps = [m.total_steps for m in metrics_list]
        step_variance = self._variance(steps)
        step_mean = sum(steps) / len(steps)
        step_consistency = max(0, 1 - (step_variance / max(step_mean, 1)))

        # Check token consistency
        tokens = [m.total_tokens for m in metrics_list]
        token_variance = self._variance(tokens)
        token_mean = sum(tokens) / len(tokens)
        token_consistency = max(0, 1 - (token_variance / max(token_mean, 1000)))

        # Weighted average
        score = (
            completion_consistency * 0.5
            + step_consistency * 0.3
            + token_consistency * 0.2
        )

        return round(score * 100, 2)


# Global analyzer instance
_analyzer: Optional[TraceAnalyzer] = None


def get_trace_analyzer() -> TraceAnalyzer:
    """Get the global trace analyzer instance."""
    global _analyzer
    if _analyzer is None:
        _analyzer = TraceAnalyzer()
    return _analyzer
