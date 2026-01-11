"""Real-time trace ingestion endpoint for external agents."""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.v1.trace_stream import notify_span_added, notify_trace_completed, notify_trace_started
from app.core.database import get_db
from app.models.trace import Trace, Span, SpanType
from app.models.user import User
from app.services.agent_service import AgentService

router = APIRouter()


class SpanData(BaseModel):
    span_type: str  # "llm", "tool", "agent", "chain"
    name: str
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    status: str = "success"  # "success", "error", "running"
    attributes: dict = {}
    parent_span_id: Optional[str] = None


class TraceIngestRequest(BaseModel):
    agent_id: str
    trace_id: Optional[str] = None  # If continuing an existing trace
    spans: List[SpanData]
    metadata: dict = {}


class TraceIngestResponse(BaseModel):
    trace_id: str
    spans_created: int
    message: str


@router.post("/ingest", response_model=TraceIngestResponse)
async def ingest_trace(
    request: TraceIngestRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TraceIngestResponse:
    """
    Ingest trace data from external agents in real-time.

    Use this endpoint to send traces from:
    - Claude Code CLI wrapper
    - Custom agents using the SDK
    - Any instrumented application
    """
    # Verify agent access
    agent_service = AgentService(db)
    agent = await agent_service.get(uuid.UUID(request.agent_id))

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    if agent.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to ingest traces for this agent",
        )

    now = datetime.now(timezone.utc)
    org_id = str(agent.organization_id)
    is_new_trace = False

    # Create or get trace
    if request.trace_id:
        # Continue existing trace
        from sqlalchemy import select
        result = await db.execute(
            select(Trace).where(Trace.id == uuid.UUID(request.trace_id))
        )
        trace = result.scalar_one_or_none()
        if not trace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Trace not found",
            )
    else:
        # Create new trace
        trace = Trace(
            id=uuid.uuid4(),
            agent_id=agent.id,
            started_at=now,
            trace_metadata=request.metadata,
        )
        db.add(trace)
        await db.flush()
        is_new_trace = True

    # Map span types to enum values
    span_type_map = {
        "llm": SpanType.LLM_CALL,
        "llm_call": SpanType.LLM_CALL,
        "tool": SpanType.TOOL_CALL,
        "tool_call": SpanType.TOOL_CALL,
        "agent": SpanType.CUSTOM,
        "chain": SpanType.CUSTOM,
        "retrieval": SpanType.API_CALL,
        "embedding": SpanType.LLM_CALL,
        "decision": SpanType.DECISION,
        "file": SpanType.FILE_OPERATION,
        "file_operation": SpanType.FILE_OPERATION,
        "api": SpanType.API_CALL,
        "api_call": SpanType.API_CALL,
        "custom": SpanType.CUSTOM,
    }

    # Create spans
    spans_created = 0
    span_id_map = {}  # Map client span IDs to DB span IDs
    created_spans = []  # Track spans for streaming

    for span_data in request.spans:
        span_type = span_type_map.get(span_data.span_type.lower(), SpanType.CUSTOM)

        # Handle parent span ID
        parent_id = None
        if span_data.parent_span_id and span_data.parent_span_id in span_id_map:
            parent_id = span_id_map[span_data.parent_span_id]

        span = Span(
            id=uuid.uuid4(),
            trace_id=trace.id,
            parent_span_id=parent_id,
            span_type=span_type,
            name=span_data.name,
            started_at=span_data.started_at or now,
            ended_at=span_data.ended_at,
            status=span_data.status,
            attributes=span_data.attributes,
        )
        db.add(span)

        # Track for parent references
        if span_data.attributes.get("client_span_id"):
            span_id_map[span_data.attributes["client_span_id"]] = span.id

        spans_created += 1
        created_spans.append({
            "id": str(span.id),
            "span_type": span_data.span_type,
            "name": span_data.name,
            "status": span_data.status,
            "attributes": span_data.attributes,
        })

    # Update trace end time if all spans are complete
    trace_completed = all(s.ended_at for s in request.spans) and len(request.spans) > 0
    if trace_completed:
        trace.ended_at = max(s.ended_at for s in request.spans if s.ended_at)

    await db.commit()

    # Stream events to connected clients (in background to not block response)
    async def emit_events():
        if is_new_trace:
            await notify_trace_started(org_id, str(trace.id), str(agent.id), agent.name)

        for span_info in created_spans:
            await notify_span_added(
                org_id,
                str(trace.id),
                span_info["id"],
                span_info["span_type"],
                span_info["name"],
                span_info["status"],
                span_info["attributes"],
            )

        if trace_completed:
            duration_ms = None
            if trace.ended_at and trace.started_at:
                duration_ms = int((trace.ended_at - trace.started_at).total_seconds() * 1000)
            await notify_trace_completed(
                org_id,
                str(trace.id),
                all(s.status == "success" for s in request.spans),
                duration_ms,
            )

    background_tasks.add_task(emit_events)

    return TraceIngestResponse(
        trace_id=str(trace.id),
        spans_created=spans_created,
        message="Trace data ingested successfully",
    )


@router.post("/span")
async def ingest_single_span(
    agent_id: str,
    trace_id: str,
    span: SpanData,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Ingest a single span for real-time streaming.

    Use this for live updates as Claude Code executes.
    """
    # Verify agent access
    agent_service = AgentService(db)
    agent = await agent_service.get(uuid.UUID(agent_id))

    if not agent or agent.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized",
        )

    org_id = str(agent.organization_id)

    # Get trace
    from sqlalchemy import select
    result = await db.execute(
        select(Trace).where(Trace.id == uuid.UUID(trace_id))
    )
    trace = result.scalar_one_or_none()
    if not trace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trace not found",
        )

    span_type_map = {
        "llm": SpanType.LLM_CALL,
        "llm_call": SpanType.LLM_CALL,
        "tool": SpanType.TOOL_CALL,
        "tool_call": SpanType.TOOL_CALL,
        "agent": SpanType.CUSTOM,
        "chain": SpanType.CUSTOM,
        "decision": SpanType.DECISION,
        "file": SpanType.FILE_OPERATION,
        "api": SpanType.API_CALL,
        "custom": SpanType.CUSTOM,
    }

    db_span = Span(
        id=uuid.uuid4(),
        trace_id=trace.id,
        span_type=span_type_map.get(span.span_type.lower(), SpanType.CUSTOM),
        name=span.name,
        started_at=span.started_at or datetime.now(timezone.utc),
        ended_at=span.ended_at,
        status=span.status,
        attributes=span.attributes,
    )
    db.add(db_span)
    await db.commit()

    # Stream event to connected clients
    background_tasks.add_task(
        notify_span_added,
        org_id,
        trace_id,
        str(db_span.id),
        span.span_type,
        span.name,
        span.status,
        span.attributes,
    )

    return {"span_id": str(db_span.id), "status": "created"}
