"""Celery tasks for trace processing."""

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID

from celery import shared_task
from celery.utils.log import get_task_logger
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_maker
from app.models.agent import Agent
from app.models.trace import Span, SpanType, Trace

logger = get_task_logger(__name__)


def run_async(coro):
    """Run async coroutine in sync context."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@shared_task(name="app.workers.trace_tasks.aggregate_trace_metrics")
def aggregate_trace_metrics() -> dict:
    """Aggregate trace metrics for observability dashboard."""
    logger.info("Aggregating trace metrics")

    async def _aggregate():
        async with async_session_maker() as db:
            now = datetime.now(timezone.utc)
            last_hour = now - timedelta(hours=1)

            # Count traces in the last hour
            trace_count = await db.scalar(
                select(func.count(Trace.id)).where(Trace.started_at >= last_hour)
            )

            # Count spans by type in the last hour
            span_counts = {}
            for span_type in SpanType:
                count = await db.scalar(
                    select(func.count(Span.id))
                    .join(Trace)
                    .where(Trace.started_at >= last_hour, Span.span_type == span_type)
                )
                span_counts[span_type.value] = count or 0

            # Get top 5 agents by trace count in the last hour
            result = await db.execute(
                select(Agent.id, Agent.name, func.count(Trace.id).label("trace_count"))
                .join(Trace)
                .where(Trace.started_at >= last_hour)
                .group_by(Agent.id)
                .order_by(func.count(Trace.id).desc())
                .limit(5)
            )
            top_agents = [
                {"agent_id": str(row[0]), "name": row[1], "trace_count": row[2]}
                for row in result.fetchall()
            ]

            # Calculate average trace duration
            avg_duration = await db.scalar(
                select(
                    func.avg(
                        func.extract("epoch", Trace.ended_at)
                        - func.extract("epoch", Trace.started_at)
                    )
                ).where(
                    Trace.started_at >= last_hour,
                    Trace.ended_at.isnot(None),
                )
            )

            metrics = {
                "period": "last_hour",
                "timestamp": now.isoformat(),
                "trace_count": trace_count or 0,
                "span_counts": span_counts,
                "top_agents": top_agents,
                "avg_duration_seconds": round(avg_duration, 2) if avg_duration else None,
            }

            logger.info(f"Metrics aggregated: {trace_count} traces in the last hour")
            return metrics

    return run_async(_aggregate())


@shared_task(
    bind=True,
    name="app.workers.trace_tasks.process_trace_batch",
    max_retries=3,
)
def process_trace_batch(self, agent_id: str, traces_data: list) -> dict:
    """Process a batch of traces asynchronously."""
    logger.info(f"Processing {len(traces_data)} traces for agent {agent_id}")

    async def _process():
        async with async_session_maker() as db:
            from app.services.trace_service import TraceService
            from app.schemas.trace import TraceBatchCreate, TraceData

            service = TraceService(db)

            batch = TraceBatchCreate(
                agent_id=UUID(agent_id),
                traces=[TraceData(**t) for t in traces_data],
            )

            result = await service.ingest_batch(batch)

            logger.info(f"Processed batch: {result.accepted} traces accepted")
            return {
                "status": "completed",
                "accepted": result.accepted,
                "errors": result.errors,
            }

    return run_async(_process())


@shared_task(name="app.workers.trace_tasks.cleanup_old_traces")
def cleanup_old_traces(days: int = 90) -> dict:
    """Clean up traces older than specified days."""
    logger.info(f"Cleaning up traces older than {days} days")

    async def _cleanup():
        async with async_session_maker() as db:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

            # Get trace IDs to delete
            result = await db.execute(
                select(Trace.id).where(Trace.started_at < cutoff_date)
            )
            trace_ids = [row[0] for row in result.fetchall()]

            if trace_ids:
                # Delete spans first (foreign key constraint)
                await db.execute(
                    delete(Span).where(Span.trace_id.in_(trace_ids))
                )

                # Delete traces
                await db.execute(
                    delete(Trace).where(Trace.id.in_(trace_ids))
                )

                await db.commit()

            logger.info(f"Deleted {len(trace_ids)} old traces")
            return {
                "deleted_count": len(trace_ids),
                "cutoff_date": cutoff_date.isoformat(),
            }

    return run_async(_cleanup())


@shared_task(
    bind=True,
    name="app.workers.trace_tasks.analyze_trace",
    max_retries=2,
)
def analyze_trace(self, trace_id: str) -> dict:
    """Analyze a single trace for anomalies and insights."""
    logger.info(f"Analyzing trace {trace_id}")

    async def _analyze():
        async with async_session_maker() as db:
            # Get trace with spans
            result = await db.execute(
                select(Trace).where(Trace.id == UUID(trace_id))
            )
            trace = result.scalar_one_or_none()

            if not trace:
                return {"error": "Trace not found"}

            # Get spans
            result = await db.execute(
                select(Span)
                .where(Span.trace_id == UUID(trace_id))
                .order_by(Span.started_at)
            )
            spans = list(result.scalars().all())

            # Calculate metrics
            analysis = {
                "trace_id": trace_id,
                "span_count": len(spans),
                "span_types": {},
                "errors": [],
                "duration_ms": None,
                "insights": [],
            }

            # Count span types
            for span in spans:
                span_type = span.span_type.value if span.span_type else "unknown"
                analysis["span_types"][span_type] = analysis["span_types"].get(span_type, 0) + 1

                # Collect errors
                if span.status == "error":
                    analysis["errors"].append({
                        "span_id": str(span.id),
                        "name": span.name,
                        "attributes": span.attributes,
                    })

            # Calculate duration
            if trace.started_at and trace.ended_at:
                analysis["duration_ms"] = int(
                    (trace.ended_at - trace.started_at).total_seconds() * 1000
                )

            # Generate insights
            if analysis["errors"]:
                analysis["insights"].append(f"Found {len(analysis['errors'])} errors in trace")

            if analysis["duration_ms"] and analysis["duration_ms"] > 60000:
                analysis["insights"].append("Trace took longer than 1 minute")

            llm_count = analysis["span_types"].get("llm_call", 0)
            if llm_count > 10:
                analysis["insights"].append(f"High LLM call count: {llm_count}")

            logger.info(f"Trace {trace_id} analyzed: {len(spans)} spans, {len(analysis['errors'])} errors")
            return analysis

    return run_async(_analyze())
