"""Trace management endpoints."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.trace import (
    SpanResponse,
    TraceBatchCreate,
    TraceBatchResponse,
    TraceListResponse,
    TraceResponse,
)
from app.services.agent_service import AgentService
from app.services.trace_service import TraceService

router = APIRouter()


@router.post("/batch", response_model=TraceBatchResponse, status_code=status.HTTP_201_CREATED)
async def ingest_traces(
    data: TraceBatchCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TraceBatchResponse:
    """Ingest a batch of traces."""
    agent_service = AgentService(db)
    trace_service = TraceService(db)

    # Verify agent belongs to user's organization
    agent = await agent_service.get(data.agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    if agent.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to submit traces for this agent",
        )

    # Ingest traces
    traces = await trace_service.ingest_batch(data)

    return TraceBatchResponse(
        accepted=len(traces),
        trace_ids=[trace.id for trace in traces],
    )


@router.get("", response_model=TraceListResponse)
async def list_traces(
    agent_id: Optional[UUID] = None,
    session_id: Optional[UUID] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TraceListResponse:
    """List traces with optional filters."""
    if not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must belong to an organization",
        )

    # If agent_id provided, verify access
    if agent_id:
        agent_service = AgentService(db)
        agent = await agent_service.get(agent_id)
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent not found",
            )
        if agent.organization_id != current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this agent's traces",
            )

    trace_service = TraceService(db)
    traces, total = await trace_service.list(
        organization_id=current_user.organization_id,
        agent_id=agent_id,
        session_id=session_id,
        page=page,
        page_size=page_size,
    )

    items = [await trace_service.to_response(trace) for trace in traces]

    return TraceListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.get("/{trace_id}", response_model=TraceResponse)
async def get_trace(
    trace_id: UUID,
    include_spans: bool = Query(True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TraceResponse:
    """Get trace details with spans."""
    trace_service = TraceService(db)
    trace = await trace_service.get(trace_id)

    if not trace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trace not found",
        )

    # Verify access through agent
    agent_service = AgentService(db)
    agent = await agent_service.get(trace.agent_id)

    if not agent or agent.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this trace",
        )

    return await trace_service.to_response(trace, include_spans=include_spans)


@router.get("/{trace_id}/spans", response_model=List[SpanResponse])
async def get_trace_spans(
    trace_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[SpanResponse]:
    """Get all spans for a trace."""
    trace_service = TraceService(db)
    trace = await trace_service.get(trace_id)

    if not trace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trace not found",
        )

    # Verify access through agent
    agent_service = AgentService(db)
    agent = await agent_service.get(trace.agent_id)

    if not agent or agent.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this trace",
        )

    spans = await trace_service.get_spans(trace_id)
    return [trace_service.span_to_response(span) for span in spans]


@router.delete("/{trace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trace(
    trace_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a trace and its spans."""
    trace_service = TraceService(db)
    trace = await trace_service.get(trace_id)

    if not trace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trace not found",
        )

    # Verify access through agent
    agent_service = AgentService(db)
    agent = await agent_service.get(trace.agent_id)

    if not agent or agent.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this trace",
        )

    await trace_service.delete(trace_id)
