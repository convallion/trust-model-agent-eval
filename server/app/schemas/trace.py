"""Trace and Span schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.trace import SpanStatus, SpanType


class SpanCreate(BaseModel):
    """Schema for creating a span."""

    span_id: Optional[UUID] = Field(default=None, description="External span ID")
    parent_span_id: Optional[UUID] = None
    span_type: SpanType
    name: str = Field(..., max_length=255)
    started_at: datetime
    ended_at: Optional[datetime] = None
    status: SpanStatus = SpanStatus.OK
    error_message: Optional[str] = None
    attributes: Dict[str, Any] = Field(default_factory=dict)


class SpanResponse(BaseModel):
    """Span information response."""

    id: UUID
    trace_id: UUID
    parent_span_id: Optional[UUID]
    span_type: SpanType
    name: str
    started_at: datetime
    ended_at: Optional[datetime]
    status: SpanStatus
    error_message: Optional[str]
    attributes: Dict[str, Any]
    duration_ms: Optional[int]

    model_config = {"from_attributes": True}


class TraceCreate(BaseModel):
    """Schema for creating a trace with spans."""

    trace_id: Optional[UUID] = Field(default=None, description="External trace ID")
    agent_id: UUID
    session_id: Optional[str] = None
    task_description: Optional[str] = None
    started_at: datetime
    ended_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    spans: List[SpanCreate] = Field(default_factory=list)


class TraceBatchCreate(BaseModel):
    """Schema for batch trace ingestion."""

    traces: List[TraceCreate]


class TraceResponse(BaseModel):
    """Trace information response."""

    id: UUID
    agent_id: UUID
    session_id: Optional[str]
    task_description: Optional[str]
    started_at: datetime
    ended_at: Optional[datetime]
    duration_ms: Optional[int]
    total_tokens: int
    total_cost_usd: Optional[float]
    tool_call_count: int
    metadata: Dict[str, Any]
    created_at: datetime

    # Spans (only included when fetching single trace)
    spans: Optional[List[SpanResponse]] = None

    model_config = {"from_attributes": True}


class TraceListResponse(BaseModel):
    """Paginated list of traces."""

    items: List[TraceResponse]
    total: int
    page: int
    page_size: int
    pages: int


class TraceSummary(BaseModel):
    """Summary statistics for traces."""

    total_traces: int
    total_spans: int
    total_tokens: int
    total_cost_usd: float
    avg_duration_ms: float
    avg_tokens_per_trace: float
    tool_calls_count: int
    llm_calls_count: int
    decision_count: int
