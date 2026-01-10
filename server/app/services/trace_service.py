"""Trace service for ingesting and querying agent traces."""

import uuid
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.trace import Span, SpanType, Trace
from app.schemas.trace import SpanCreate, TraceCreate, TraceResponse


class TraceService:
    """Service for trace management operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: TraceCreate) -> Trace:
        """Create a new trace with spans."""
        # Calculate aggregated metrics
        total_tokens = 0
        total_cost = 0.0
        tool_call_count = 0

        for span_data in data.spans:
            if span_data.span_type == SpanType.LLM_CALL:
                attrs = span_data.attributes
                total_tokens += attrs.get("prompt_tokens", 0)
                total_tokens += attrs.get("completion_tokens", 0)
                total_cost += attrs.get("cost_usd", 0.0)
            elif span_data.span_type == SpanType.TOOL_CALL:
                tool_call_count += 1

        # Create trace
        trace = Trace(
            id=data.trace_id or uuid.uuid4(),
            agent_id=data.agent_id,
            session_id=data.session_id,
            task_description=data.task_description,
            started_at=data.started_at,
            ended_at=data.ended_at,
            total_tokens=total_tokens,
            total_cost_usd=total_cost if total_cost > 0 else None,
            tool_call_count=tool_call_count,
            trace_metadata=data.metadata,
        )
        self.db.add(trace)
        await self.db.flush()

        # Create spans
        for span_data in data.spans:
            span = Span(
                id=span_data.span_id or uuid.uuid4(),
                trace_id=trace.id,
                parent_span_id=span_data.parent_span_id,
                span_type=span_data.span_type,
                name=span_data.name,
                started_at=span_data.started_at,
                ended_at=span_data.ended_at,
                status=span_data.status,
                error_message=span_data.error_message,
                attributes=span_data.attributes,
            )
            self.db.add(span)

        await self.db.flush()
        return trace

    async def create_batch(self, traces: List[TraceCreate]) -> List[Trace]:
        """Create multiple traces in batch."""
        result = []
        for trace_data in traces:
            trace = await self.create(trace_data)
            result.append(trace)
        return result

    async def get(self, trace_id: uuid.UUID) -> Optional[Trace]:
        """Get a trace by ID with spans."""
        result = await self.db.execute(
            select(Trace)
            .where(Trace.id == trace_id)
            .options(joinedload(Trace.spans))
        )
        return result.scalar_one_or_none()

    async def list_for_agent(
        self,
        agent_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
        session_id: Optional[str] = None,
    ) -> Tuple[List[Trace], int]:
        """List traces for an agent with pagination."""
        query = select(Trace).where(Trace.agent_id == agent_id)

        if session_id:
            query = query.where(Trace.session_id == session_id)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.scalar(count_query) or 0

        # Get paginated results
        query = (
            query.order_by(Trace.started_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(query)
        traces = list(result.scalars().all())

        return traces, total

    async def get_summary(self, agent_id: uuid.UUID) -> dict:
        """Get trace summary statistics for an agent."""
        # Total traces and spans
        trace_count = await self.db.scalar(
            select(func.count()).where(Trace.agent_id == agent_id)
        ) or 0

        span_count = await self.db.scalar(
            select(func.count())
            .select_from(Span)
            .join(Trace)
            .where(Trace.agent_id == agent_id)
        ) or 0

        # Aggregate metrics
        agg_result = await self.db.execute(
            select(
                func.sum(Trace.total_tokens),
                func.sum(Trace.total_cost_usd),
                func.sum(Trace.tool_call_count),
            ).where(Trace.agent_id == agent_id)
        )
        row = agg_result.one()
        total_tokens = row[0] or 0
        total_cost = row[1] or 0.0
        tool_calls = row[2] or 0

        # Average duration
        avg_duration_result = await self.db.execute(
            select(
                func.avg(
                    func.extract("epoch", Trace.ended_at - Trace.started_at) * 1000
                )
            )
            .where(Trace.agent_id == agent_id)
            .where(Trace.ended_at.isnot(None))
        )
        avg_duration = avg_duration_result.scalar() or 0

        # Span type counts
        llm_calls = await self.db.scalar(
            select(func.count())
            .select_from(Span)
            .join(Trace)
            .where(Trace.agent_id == agent_id)
            .where(Span.span_type == SpanType.LLM_CALL)
        ) or 0

        decisions = await self.db.scalar(
            select(func.count())
            .select_from(Span)
            .join(Trace)
            .where(Trace.agent_id == agent_id)
            .where(Span.span_type == SpanType.DECISION)
        ) or 0

        return {
            "total_traces": trace_count,
            "total_spans": span_count,
            "total_tokens": total_tokens,
            "total_cost_usd": float(total_cost),
            "avg_duration_ms": float(avg_duration),
            "avg_tokens_per_trace": total_tokens / trace_count if trace_count > 0 else 0,
            "tool_calls_count": tool_calls,
            "llm_calls_count": llm_calls,
            "decision_count": decisions,
        }

    def to_response(self, trace: Trace, include_spans: bool = False) -> TraceResponse:
        """Convert trace model to response schema."""
        data = {
            "id": trace.id,
            "agent_id": trace.agent_id,
            "session_id": trace.session_id,
            "task_description": trace.task_description,
            "started_at": trace.started_at,
            "ended_at": trace.ended_at,
            "duration_ms": trace.duration_ms,
            "total_tokens": trace.total_tokens,
            "total_cost_usd": trace.total_cost_usd,
            "tool_call_count": trace.tool_call_count,
            "metadata": trace.trace_metadata,
            "created_at": trace.created_at,
        }

        if include_spans and trace.spans:
            data["spans"] = [
                {
                    "id": span.id,
                    "trace_id": span.trace_id,
                    "parent_span_id": span.parent_span_id,
                    "span_type": span.span_type,
                    "name": span.name,
                    "started_at": span.started_at,
                    "ended_at": span.ended_at,
                    "status": span.status,
                    "error_message": span.error_message,
                    "attributes": span.attributes,
                    "duration_ms": span.duration_ms,
                }
                for span in trace.spans
            ]

        return TraceResponse(**data)
