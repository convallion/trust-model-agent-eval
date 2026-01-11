"""Evaluation service for running and managing agent evaluations."""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.evaluation import EvaluationGrade, EvaluationRun, EvaluationStatus
from app.schemas.evaluation import EvaluationConfig, EvaluationRequest, EvaluationResponse


class EvaluationService:
    """Service for evaluation management operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: EvaluationRequest) -> EvaluationRun:
        """Create a new evaluation run."""
        evaluation = EvaluationRun(
            agent_id=data.agent_id,
            suites=data.suites,
            config=data.config.model_dump(),
            status=EvaluationStatus.PENDING,
        )
        self.db.add(evaluation)
        await self.db.flush()
        return evaluation

    async def get(self, evaluation_id: uuid.UUID) -> Optional[EvaluationRun]:
        """Get an evaluation by ID."""
        result = await self.db.execute(
            select(EvaluationRun)
            .where(EvaluationRun.id == evaluation_id)
            .options(joinedload(EvaluationRun.agent))
        )
        return result.scalar_one_or_none()

    async def list_for_agent(
        self,
        agent_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
        status: Optional[EvaluationStatus] = None,
    ) -> Tuple[List[EvaluationRun], int]:
        """List evaluations for an agent with pagination."""
        query = select(EvaluationRun).where(EvaluationRun.agent_id == agent_id)

        if status:
            query = query.where(EvaluationRun.status == status)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.scalar(count_query) or 0

        # Get paginated results
        query = (
            query.order_by(EvaluationRun.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(query)
        evaluations = list(result.scalars().all())

        return evaluations, total

    async def list(
        self,
        organization_id: uuid.UUID,
        agent_id: Optional[uuid.UUID] = None,
        status: Optional[EvaluationStatus] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[EvaluationRun], int]:
        """List evaluations for an organization with pagination."""
        from app.models.agent import Agent

        query = (
            select(EvaluationRun)
            .join(Agent, EvaluationRun.agent_id == Agent.id)
            .where(Agent.organization_id == organization_id)
        )

        if agent_id:
            query = query.where(EvaluationRun.agent_id == agent_id)

        if status:
            query = query.where(EvaluationRun.status == status)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.scalar(count_query) or 0

        # Get paginated results
        query = (
            query.order_by(EvaluationRun.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(query)
        evaluations = list(result.scalars().all())

        return evaluations, total

    async def run_evaluation(self, evaluation_id: uuid.UUID) -> None:
        """Run the actual evaluation (mock implementation for demo)."""
        import asyncio
        import random

        evaluation = await self.get(evaluation_id)
        if not evaluation:
            return

        # Mark as started
        await self.start(evaluation_id)
        await self.db.commit()

        # Simulate running evaluation suites
        results = {}
        for i, suite in enumerate(evaluation.suites):
            await self.update_progress(
                evaluation_id,
                progress_percent=int((i / len(evaluation.suites)) * 100),
                current_suite=suite,
                current_test=f"Running {suite} tests...",
            )
            await self.db.commit()

            # Simulate test execution time
            await asyncio.sleep(1)

            # Generate mock scores (for demo purposes)
            # In a real implementation, this would run actual evaluation tasks
            base_score = random.uniform(70, 95)
            results[suite] = {
                "score": base_score,
                "tests_passed": random.randint(15, 20),
                "tests_failed": random.randint(0, 5),
                "tests_total": 20,
                "details": {
                    "test_1": {"passed": True, "score": random.uniform(0.7, 1.0)},
                    "test_2": {"passed": True, "score": random.uniform(0.7, 1.0)},
                    "test_3": {"passed": random.random() > 0.2, "score": random.uniform(0.5, 1.0)},
                }
            }

        # Complete the evaluation
        await self.complete(evaluation_id, results)
        await self.db.commit()

    async def start(self, evaluation_id: uuid.UUID) -> Optional[EvaluationRun]:
        """Mark evaluation as started."""
        evaluation = await self.get(evaluation_id)
        if not evaluation:
            return None

        evaluation.status = EvaluationStatus.RUNNING
        evaluation.started_at = datetime.now(timezone.utc)
        await self.db.flush()
        return evaluation

    async def update_progress(
        self,
        evaluation_id: uuid.UUID,
        progress_percent: int,
        current_suite: Optional[str] = None,
        current_test: Optional[str] = None,
    ) -> None:
        """Update evaluation progress."""
        evaluation = await self.get(evaluation_id)
        if evaluation:
            evaluation.progress_percent = progress_percent
            evaluation.current_suite = current_suite
            evaluation.current_test = current_test
            await self.db.flush()

    async def complete(
        self,
        evaluation_id: uuid.UUID,
        results: Dict[str, Any],
    ) -> Optional[EvaluationRun]:
        """Complete an evaluation with results."""
        evaluation = await self.get(evaluation_id)
        if not evaluation:
            return None

        # Calculate scores
        overall_score = self._calculate_overall_score(results)
        grade = EvaluationRun.calculate_grade(overall_score)

        # Extract suite scores
        capability_score = results.get("capability", {}).get("score")
        safety_score = results.get("safety", {}).get("score")
        reliability_score = results.get("reliability", {}).get("score")
        communication_score = results.get("communication", {}).get("score")

        # Check certificate eligibility
        certificate_eligible = EvaluationRun.is_eligible_for_certificate(
            overall_score, safety_score
        )

        evaluation.status = EvaluationStatus.COMPLETED
        evaluation.completed_at = datetime.now(timezone.utc)
        evaluation.progress_percent = 100
        evaluation.overall_score = overall_score
        evaluation.grade = grade
        evaluation.certificate_eligible = certificate_eligible
        evaluation.capability_score = capability_score
        evaluation.safety_score = safety_score
        evaluation.reliability_score = reliability_score
        evaluation.communication_score = communication_score
        evaluation.results = results

        await self.db.flush()
        return evaluation

    async def fail(
        self,
        evaluation_id: uuid.UUID,
        error_message: str,
    ) -> Optional[EvaluationRun]:
        """Mark evaluation as failed."""
        evaluation = await self.get(evaluation_id)
        if not evaluation:
            return None

        evaluation.status = EvaluationStatus.FAILED
        evaluation.completed_at = datetime.now(timezone.utc)
        evaluation.error_message = error_message

        await self.db.flush()
        return evaluation

    async def cancel(self, evaluation_id: uuid.UUID) -> Optional[EvaluationRun]:
        """Cancel a pending or running evaluation."""
        evaluation = await self.get(evaluation_id)
        if not evaluation:
            return None

        if evaluation.status not in [EvaluationStatus.PENDING, EvaluationStatus.RUNNING]:
            return None

        evaluation.status = EvaluationStatus.CANCELLED
        evaluation.completed_at = datetime.now(timezone.utc)

        await self.db.flush()
        return evaluation

    def _calculate_overall_score(self, results: Dict[str, Any]) -> float:
        """Calculate overall score from suite results."""
        weights = {
            "capability": 0.3,
            "safety": 0.35,  # Safety weighted highest
            "reliability": 0.2,
            "communication": 0.15,
        }

        total_weight = 0.0
        weighted_sum = 0.0

        for suite, weight in weights.items():
            if suite in results and "score" in results[suite]:
                score = results[suite]["score"]
                weighted_sum += score * weight
                total_weight += weight

        if total_weight == 0:
            return 0.0

        return weighted_sum / total_weight

    def to_response(self, evaluation: EvaluationRun) -> EvaluationResponse:
        """Convert evaluation model to response schema."""
        return EvaluationResponse(
            id=evaluation.id,
            agent_id=evaluation.agent_id,
            status=evaluation.status,
            suites=evaluation.suites,
            config=evaluation.config,
            started_at=evaluation.started_at,
            completed_at=evaluation.completed_at,
            duration_seconds=evaluation.duration_seconds,
            created_at=evaluation.created_at,
            progress_percent=evaluation.progress_percent,
            current_suite=evaluation.current_suite,
            current_test=evaluation.current_test,
            overall_score=float(evaluation.overall_score) if evaluation.overall_score else None,
            grade=evaluation.grade,
            certificate_eligible=evaluation.certificate_eligible,
            capability_score=(
                float(evaluation.capability_score) if evaluation.capability_score else None
            ),
            safety_score=float(evaluation.safety_score) if evaluation.safety_score else None,
            reliability_score=(
                float(evaluation.reliability_score) if evaluation.reliability_score else None
            ),
            communication_score=(
                float(evaluation.communication_score) if evaluation.communication_score else None
            ),
            results=evaluation.results,
            error_message=evaluation.error_message,
        )
