"""Statistics and metrics endpoints for dashboard and observability."""

from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.agent import Agent
from app.models.certificate import Certificate
from app.models.evaluation import EvaluationRun, EvaluationStatus
from app.models.trace import Span, Trace
from app.models.user import User

router = APIRouter()


class DashboardStats(BaseModel):
    total_agents: int
    active_agents: int
    total_traces: int
    total_evaluations: int
    completed_evaluations: int
    total_certificates: int
    active_certificates: int
    avg_trust_score: Optional[float]
    agents_by_grade: dict


class TimeSeriesPoint(BaseModel):
    timestamp: str
    value: int


class ObservabilityMetrics(BaseModel):
    total_requests: int
    success_count: int
    error_count: int
    avg_latency_ms: float
    success_rate: float
    requests_over_time: List[TimeSeriesPoint]
    errors_over_time: List[TimeSeriesPoint]
    latency_over_time: List[TimeSeriesPoint]
    top_agents: List[dict]
    recent_errors: List[dict]
    span_type_breakdown: dict


class AgentStats(BaseModel):
    agent_id: str
    agent_name: str
    total_traces: int
    total_spans: int
    avg_latency_ms: float
    success_rate: float
    last_activity: Optional[str]


@router.get("/dashboard", response_model=DashboardStats)
async def get_dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DashboardStats:
    """Get overview statistics for the dashboard."""
    org_id = current_user.organization_id

    # Total agents
    total_agents = await db.scalar(
        select(func.count(Agent.id)).where(Agent.organization_id == org_id)
    ) or 0

    # Active agents (with recent traces in last 24h)
    day_ago = datetime.now(timezone.utc) - timedelta(days=1)
    active_agents_query = (
        select(func.count(func.distinct(Trace.agent_id)))
        .select_from(Trace)
        .join(Agent, Trace.agent_id == Agent.id)
        .where(
            and_(
                Agent.organization_id == org_id,
                Trace.started_at >= day_ago,
            )
        )
    )
    active_agents = await db.scalar(active_agents_query) or 0

    # Total traces
    total_traces = await db.scalar(
        select(func.count(Trace.id))
        .select_from(Trace)
        .join(Agent, Trace.agent_id == Agent.id)
        .where(Agent.organization_id == org_id)
    ) or 0

    # Total evaluations
    total_evaluations = await db.scalar(
        select(func.count(EvaluationRun.id))
        .select_from(EvaluationRun)
        .join(Agent, EvaluationRun.agent_id == Agent.id)
        .where(Agent.organization_id == org_id)
    ) or 0

    # Completed evaluations
    completed_evaluations = await db.scalar(
        select(func.count(EvaluationRun.id))
        .select_from(EvaluationRun)
        .join(Agent, EvaluationRun.agent_id == Agent.id)
        .where(
            and_(
                Agent.organization_id == org_id,
                EvaluationRun.status == EvaluationStatus.COMPLETED,
            )
        )
    ) or 0

    # Total certificates
    total_certificates = await db.scalar(
        select(func.count(Certificate.id))
        .select_from(Certificate)
        .join(Agent, Certificate.agent_id == Agent.id)
        .where(Agent.organization_id == org_id)
    ) or 0

    # Active certificates
    active_certificates = await db.scalar(
        select(func.count(Certificate.id))
        .select_from(Certificate)
        .join(Agent, Certificate.agent_id == Agent.id)
        .where(
            and_(
                Agent.organization_id == org_id,
                Certificate.status == "active",
                Certificate.expires_at > datetime.now(timezone.utc),
            )
        )
    ) or 0

    # Average trust score
    avg_score_result = await db.scalar(
        select(func.avg(Certificate.overall_score))
        .select_from(Certificate)
        .join(Agent, Certificate.agent_id == Agent.id)
        .where(
            and_(
                Agent.organization_id == org_id,
                Certificate.status == "active",
            )
        )
    )
    avg_trust_score = float(avg_score_result) if avg_score_result else None

    # Agents by grade
    grades_query = (
        select(Certificate.grade, func.count(Certificate.id))
        .select_from(Certificate)
        .join(Agent, Certificate.agent_id == Agent.id)
        .where(
            and_(
                Agent.organization_id == org_id,
                Certificate.status == "active",
            )
        )
        .group_by(Certificate.grade)
    )
    grades_result = await db.execute(grades_query)
    agents_by_grade = {row[0].value if row[0] else "none": row[1] for row in grades_result.fetchall()}

    return DashboardStats(
        total_agents=total_agents,
        active_agents=active_agents,
        total_traces=total_traces,
        total_evaluations=total_evaluations,
        completed_evaluations=completed_evaluations,
        total_certificates=total_certificates,
        active_certificates=active_certificates,
        avg_trust_score=avg_trust_score,
        agents_by_grade=agents_by_grade,
    )


@router.get("/observability", response_model=ObservabilityMetrics)
async def get_observability_metrics(
    hours: int = Query(24, ge=1, le=168),
    agent_id: Optional[UUID] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ObservabilityMetrics:
    """Get observability metrics for monitoring."""
    org_id = current_user.organization_id
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    # Base query for traces
    base_filter = and_(
        Agent.organization_id == org_id,
        Trace.started_at >= since,
    )
    if agent_id:
        base_filter = and_(base_filter, Trace.agent_id == agent_id)

    # Total requests (traces)
    total_requests = await db.scalar(
        select(func.count(Trace.id))
        .select_from(Trace)
        .join(Agent, Trace.agent_id == Agent.id)
        .where(base_filter)
    ) or 0

    # Get spans for detailed metrics
    spans_query = (
        select(Span)
        .select_from(Span)
        .join(Trace, Span.trace_id == Trace.id)
        .join(Agent, Trace.agent_id == Agent.id)
        .where(base_filter)
    )
    spans_result = await db.execute(spans_query)
    spans = list(spans_result.scalars().all())

    # Calculate metrics from spans
    success_count = sum(1 for s in spans if s.status == "success" or s.status == "ok")
    error_count = sum(1 for s in spans if s.status == "error")

    latencies = []
    for s in spans:
        if s.started_at and s.ended_at:
            latency = (s.ended_at - s.started_at).total_seconds() * 1000
            latencies.append(latency)

    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    total_spans = len(spans)
    success_rate = (success_count / total_spans * 100) if total_spans > 0 else 100

    # Time series data (hourly buckets)
    requests_over_time = []
    errors_over_time = []
    latency_over_time = []

    for i in range(min(hours, 24)):
        bucket_start = datetime.now(timezone.utc) - timedelta(hours=i+1)
        bucket_end = datetime.now(timezone.utc) - timedelta(hours=i)

        bucket_traces = await db.scalar(
            select(func.count(Trace.id))
            .select_from(Trace)
            .join(Agent, Trace.agent_id == Agent.id)
            .where(
                and_(
                    base_filter,
                    Trace.started_at >= bucket_start,
                    Trace.started_at < bucket_end,
                )
            )
        ) or 0

        bucket_errors = await db.scalar(
            select(func.count(Span.id))
            .select_from(Span)
            .join(Trace, Span.trace_id == Trace.id)
            .join(Agent, Trace.agent_id == Agent.id)
            .where(
                and_(
                    base_filter,
                    Span.started_at >= bucket_start,
                    Span.started_at < bucket_end,
                    Span.status == "error",
                )
            )
        ) or 0

        timestamp = bucket_end.strftime("%H:%M")
        requests_over_time.append(TimeSeriesPoint(timestamp=timestamp, value=bucket_traces))
        errors_over_time.append(TimeSeriesPoint(timestamp=timestamp, value=bucket_errors))
        latency_over_time.append(TimeSeriesPoint(timestamp=timestamp, value=int(avg_latency)))

    requests_over_time.reverse()
    errors_over_time.reverse()
    latency_over_time.reverse()

    # Top agents by activity
    top_agents_query = (
        select(Agent.id, Agent.name, func.count(Trace.id).label("trace_count"))
        .select_from(Agent)
        .outerjoin(Trace, and_(Trace.agent_id == Agent.id, Trace.started_at >= since))
        .where(Agent.organization_id == org_id)
        .group_by(Agent.id, Agent.name)
        .order_by(func.count(Trace.id).desc())
        .limit(5)
    )
    top_agents_result = await db.execute(top_agents_query)
    top_agents = [
        {"id": str(row[0]), "name": row[1], "trace_count": row[2]}
        for row in top_agents_result.fetchall()
    ]

    # Recent errors
    recent_errors_query = (
        select(Span, Trace, Agent)
        .select_from(Span)
        .join(Trace, Span.trace_id == Trace.id)
        .join(Agent, Trace.agent_id == Agent.id)
        .where(
            and_(
                Agent.organization_id == org_id,
                Span.status == "error",
            )
        )
        .order_by(Span.started_at.desc())
        .limit(10)
    )
    recent_errors_result = await db.execute(recent_errors_query)
    recent_errors = []
    for row in recent_errors_result.fetchall():
        span, trace, agent = row
        error_msg = span.attributes.get("error", "Unknown error") if span.attributes else "Unknown error"
        recent_errors.append({
            "id": str(span.id),
            "message": error_msg,
            "agent_name": agent.name,
            "trace_id": str(trace.id),
            "timestamp": span.started_at.isoformat() if span.started_at else None,
        })

    # Span type breakdown
    span_types_query = (
        select(Span.span_type, func.count(Span.id))
        .select_from(Span)
        .join(Trace, Span.trace_id == Trace.id)
        .join(Agent, Trace.agent_id == Agent.id)
        .where(base_filter)
        .group_by(Span.span_type)
    )
    span_types_result = await db.execute(span_types_query)
    span_type_breakdown = {row[0]: row[1] for row in span_types_result.fetchall()}

    return ObservabilityMetrics(
        total_requests=total_requests,
        success_count=success_count,
        error_count=error_count,
        avg_latency_ms=avg_latency,
        success_rate=success_rate,
        requests_over_time=requests_over_time,
        errors_over_time=errors_over_time,
        latency_over_time=latency_over_time,
        top_agents=top_agents,
        recent_errors=recent_errors,
        span_type_breakdown=span_type_breakdown,
    )


@router.get("/agents/{agent_id}", response_model=AgentStats)
async def get_agent_stats(
    agent_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AgentStats:
    """Get detailed stats for a specific agent."""
    org_id = current_user.organization_id

    # Verify agent access
    agent = await db.scalar(
        select(Agent).where(
            and_(Agent.id == agent_id, Agent.organization_id == org_id)
        )
    )
    if not agent:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    # Total traces
    total_traces = await db.scalar(
        select(func.count(Trace.id)).where(Trace.agent_id == agent_id)
    ) or 0

    # Total spans
    total_spans = await db.scalar(
        select(func.count(Span.id))
        .select_from(Span)
        .join(Trace, Span.trace_id == Trace.id)
        .where(Trace.agent_id == agent_id)
    ) or 0

    # Get spans for metrics
    spans_result = await db.execute(
        select(Span)
        .select_from(Span)
        .join(Trace, Span.trace_id == Trace.id)
        .where(Trace.agent_id == agent_id)
    )
    spans = list(spans_result.scalars().all())

    # Calculate metrics
    latencies = []
    success_count = 0
    for s in spans:
        if s.status in ("success", "ok"):
            success_count += 1
        if s.started_at and s.ended_at:
            latency = (s.ended_at - s.started_at).total_seconds() * 1000
            latencies.append(latency)

    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    success_rate = (success_count / len(spans) * 100) if spans else 100

    # Last activity
    last_trace = await db.scalar(
        select(Trace.started_at)
        .where(Trace.agent_id == agent_id)
        .order_by(Trace.started_at.desc())
        .limit(1)
    )

    return AgentStats(
        agent_id=str(agent_id),
        agent_name=agent.name,
        total_traces=total_traces,
        total_spans=total_spans,
        avg_latency_ms=avg_latency,
        success_rate=success_rate,
        last_activity=last_trace.isoformat() if last_trace else None,
    )
