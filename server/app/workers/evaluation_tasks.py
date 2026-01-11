"""Celery tasks for evaluation processing."""

import asyncio
from datetime import datetime, timezone
from uuid import UUID

from celery import shared_task
from celery.utils.log import get_task_logger
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_maker
from app.models.certificate import Certificate, CertificateStatus
from app.models.evaluation import EvaluationRun, EvaluationStatus

logger = get_task_logger(__name__)


def run_async(coro):
    """Run async coroutine in sync context."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@shared_task(
    bind=True,
    name="app.workers.evaluation_tasks.run_evaluation_task",
    max_retries=3,
    default_retry_delay=60,
)
def run_evaluation_task(self, evaluation_id: str) -> dict:
    """
    Run an evaluation in the background.

    This task:
    1. Loads the evaluation configuration
    2. Runs each evaluation suite (capability, safety, reliability, communication)
    3. Grades the results
    4. Updates the evaluation with final scores
    """
    logger.info(f"Starting evaluation {evaluation_id}")

    async def _run():
        async with async_session_maker() as db:
            # Get the evaluation
            result = await db.execute(
                select(EvaluationRun).where(EvaluationRun.id == UUID(evaluation_id))
            )
            evaluation = result.scalar_one_or_none()

            if not evaluation:
                logger.error(f"Evaluation {evaluation_id} not found")
                return {"error": "Evaluation not found"}

            # Update status to running
            evaluation.status = EvaluationStatus.running
            await db.commit()

            try:
                # Import evaluation engine
                from app.evaluation.engine import EvaluationEngine

                engine = EvaluationEngine(db)
                results = await engine.run_evaluation(
                    evaluation_id=evaluation.id,
                    agent_id=evaluation.agent_id,
                    suites=evaluation.suites or [],
                    config=evaluation.config or {},
                )

                # Update evaluation with results
                evaluation.status = EvaluationStatus.completed
                evaluation.completed_at = datetime.now(timezone.utc)
                evaluation.results = results

                # Calculate overall scores
                suite_scores = results.get("suite_scores", {})
                if suite_scores:
                    evaluation.overall_score = sum(suite_scores.values()) / len(suite_scores)
                    evaluation.capability_score = suite_scores.get("capability")
                    evaluation.safety_score = suite_scores.get("safety")
                    evaluation.reliability_score = suite_scores.get("reliability")
                    evaluation.communication_score = suite_scores.get("communication")

                    # Determine grade
                    evaluation.grade = _calculate_grade(evaluation.overall_score)

                await db.commit()

                logger.info(f"Evaluation {evaluation_id} completed with grade {evaluation.grade}")
                return {
                    "status": "completed",
                    "grade": evaluation.grade,
                    "overall_score": evaluation.overall_score,
                }

            except Exception as e:
                logger.exception(f"Evaluation {evaluation_id} failed: {e}")
                evaluation.status = EvaluationStatus.failed
                evaluation.results = {"error": str(e)}
                await db.commit()
                raise

    return run_async(_run())


@shared_task(name="app.workers.evaluation_tasks.cleanup_expired_certificates")
def cleanup_expired_certificates() -> dict:
    """Mark expired certificates as expired."""
    logger.info("Running certificate cleanup")

    async def _cleanup():
        async with async_session_maker() as db:
            now = datetime.now(timezone.utc)

            # Find and update expired certificates
            result = await db.execute(
                update(Certificate)
                .where(
                    Certificate.status == CertificateStatus.ACTIVE,
                    Certificate.expires_at < now,
                )
                .values(status=CertificateStatus.EXPIRED)
                .returning(Certificate.id)
            )

            expired_ids = [str(row[0]) for row in result.fetchall()]
            await db.commit()

            logger.info(f"Marked {len(expired_ids)} certificates as expired")
            return {"expired_count": len(expired_ids), "certificate_ids": expired_ids}

    return run_async(_cleanup())


@shared_task(
    bind=True,
    name="app.workers.evaluation_tasks.issue_certificate_task",
    max_retries=3,
)
def issue_certificate_task(self, agent_id: str, evaluation_id: str) -> dict:
    """Issue a certificate based on evaluation results."""
    logger.info(f"Issuing certificate for agent {agent_id}")

    async def _issue():
        async with async_session_maker() as db:
            from app.services.certificate_service import CertificateService
            from app.schemas.certificate import CertificateCreate

            service = CertificateService(db)

            cert = await service.issue(
                CertificateCreate(
                    agent_id=UUID(agent_id),
                    evaluation_id=UUID(evaluation_id),
                )
            )

            if cert:
                logger.info(f"Certificate issued: {cert.id}")
                return {
                    "certificate_id": str(cert.id),
                    "grade": cert.grade,
                    "status": "issued",
                }
            else:
                return {"status": "failed", "error": "Could not issue certificate"}

    return run_async(_issue())


def _calculate_grade(score: float) -> str:
    """Calculate letter grade from numerical score."""
    if score >= 90:
        return "A"
    elif score >= 80:
        return "B"
    elif score >= 70:
        return "C"
    elif score >= 60:
        return "D"
    else:
        return "F"
