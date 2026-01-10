"""Trace and Span data models."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class SpanType(str, Enum):
    """Types of spans in a trace."""

    llm_call = "llm_call"
    tool_call = "tool_call"
    agent_action = "agent_action"
    user_input = "user_input"
    system = "system"
    custom = "custom"


class SpanStatus(str, Enum):
    """Status of a span."""

    ok = "ok"
    error = "error"
    cancelled = "cancelled"


class SpanCreate(BaseModel):
    """Request to create a span."""

    span_id: UUID = Field(default_factory=uuid4)
    parent_span_id: Optional[UUID] = None
    span_type: SpanType
    name: str = Field(..., min_length=1, max_length=255)
    started_at: datetime
    ended_at: Optional[datetime] = None
    status: SpanStatus = SpanStatus.ok
    attributes: dict[str, Any] = Field(default_factory=dict)

    # LLM-specific attributes
    model: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    prompt: Optional[str] = None
    response: Optional[str] = None

    # Tool-specific attributes
    tool_name: Optional[str] = None
    tool_input: Optional[dict[str, Any]] = None
    tool_output: Optional[Any] = None

    # Error info
    error_message: Optional[str] = None
    error_type: Optional[str] = None


class Span(SpanCreate):
    """Full span representation including trace context."""

    trace_id: UUID

    class Config:
        from_attributes = True

    @property
    def duration_ms(self) -> Optional[float]:
        """Calculate span duration in milliseconds."""
        if self.ended_at and self.started_at:
            delta = self.ended_at - self.started_at
            return delta.total_seconds() * 1000
        return None


class TraceCreate(BaseModel):
    """Request to create a trace with spans."""

    trace_id: UUID = Field(default_factory=uuid4)
    session_id: Optional[UUID] = None
    started_at: datetime
    ended_at: Optional[datetime] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    spans: list[SpanCreate] = Field(default_factory=list)


class Trace(BaseModel):
    """Full trace representation."""

    id: UUID
    agent_id: UUID
    session_id: Optional[UUID] = None
    started_at: datetime
    ended_at: Optional[datetime] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    spans: list[Span] = Field(default_factory=list)
    created_at: datetime

    class Config:
        from_attributes = True

    @property
    def duration_ms(self) -> Optional[float]:
        """Calculate trace duration in milliseconds."""
        if self.ended_at and self.started_at:
            delta = self.ended_at - self.started_at
            return delta.total_seconds() * 1000
        return None

    @property
    def span_count(self) -> int:
        """Get number of spans."""
        return len(self.spans)

    @property
    def llm_calls(self) -> list[Span]:
        """Get all LLM call spans."""
        return [s for s in self.spans if s.span_type == SpanType.llm_call]

    @property
    def tool_calls(self) -> list[Span]:
        """Get all tool call spans."""
        return [s for s in self.spans if s.span_type == SpanType.tool_call]

    @property
    def total_tokens(self) -> int:
        """Calculate total tokens across all LLM calls."""
        total = 0
        for span in self.llm_calls:
            if span.input_tokens:
                total += span.input_tokens
            if span.output_tokens:
                total += span.output_tokens
        return total

    @property
    def has_errors(self) -> bool:
        """Check if any span has an error."""
        return any(s.status == SpanStatus.error for s in self.spans)

    def get_span(self, span_id: UUID) -> Optional[Span]:
        """Get a span by ID."""
        for span in self.spans:
            if span.span_id == span_id:
                return span
        return None

    def get_root_spans(self) -> list[Span]:
        """Get all root spans (spans without parent)."""
        return [s for s in self.spans if s.parent_span_id is None]

    def get_child_spans(self, parent_id: UUID) -> list[Span]:
        """Get all child spans of a parent."""
        return [s for s in self.spans if s.parent_span_id == parent_id]


class TraceBatch(BaseModel):
    """Batch of traces for bulk ingestion."""

    agent_id: UUID
    traces: list[TraceCreate]


class TraceBatchResponse(BaseModel):
    """Response from trace batch ingestion."""

    accepted: int
    trace_ids: list[UUID]
