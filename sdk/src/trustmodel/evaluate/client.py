"""Evaluation client for triggering and monitoring evaluations."""

from __future__ import annotations

import asyncio
from typing import Any, Optional
from uuid import UUID

from trustmodel.api.client import TrustModelClient, get_client
from trustmodel.core.config import get_config
from trustmodel.core.exceptions import EvaluationError
from trustmodel.core.logging import get_logger
from trustmodel.models.evaluation import (
    Evaluation,
    EvaluationRequest,
    EvaluationStatus,
    EvaluationSuite,
)

logger = get_logger(__name__)


class EvaluationClient:
    """Client for managing agent evaluations."""

    def __init__(self, client: Optional[TrustModelClient] = None) -> None:
        self._client = client or get_client()

    async def start(
        self,
        agent_id: UUID,
        suites: Optional[list[EvaluationSuite | str]] = None,
        config: Optional[dict[str, Any]] = None,
        trace_ids: Optional[list[UUID]] = None,
    ) -> Evaluation:
        """
        Start an evaluation run for an agent.

        Args:
            agent_id: The agent to evaluate
            suites: List of evaluation suites to run (default: all)
            config: Optional configuration for the evaluation
            trace_ids: Optional trace IDs to use as context

        Returns:
            Evaluation object with status and ID
        """
        # Convert string suite names to enums
        suite_enums = []
        if suites:
            for suite in suites:
                if isinstance(suite, str):
                    suite_enums.append(EvaluationSuite(suite))
                else:
                    suite_enums.append(suite)
        else:
            suite_enums = list(EvaluationSuite)

        request_data = {
            "agent_id": str(agent_id),
            "suites": [s.value for s in suite_enums],
            "config": config or {},
        }
        if trace_ids:
            request_data["trace_ids"] = [str(tid) for tid in trace_ids]

        response = await self._client.start_evaluation(request_data)

        logger.info(
            "Started evaluation",
            evaluation_id=response["id"],
            agent_id=str(agent_id),
            suites=[s.value for s in suite_enums],
        )

        return self._parse_evaluation(response)

    async def get(self, evaluation_id: UUID) -> Evaluation:
        """Get evaluation details and results."""
        response = await self._client.get_evaluation(evaluation_id)
        return self._parse_evaluation(response)

    async def wait_for_completion(
        self,
        evaluation_id: UUID,
        poll_interval: float = 5.0,
        timeout: float = 600.0,
    ) -> Evaluation:
        """
        Wait for an evaluation to complete.

        Args:
            evaluation_id: The evaluation to wait for
            poll_interval: Seconds between status checks
            timeout: Maximum time to wait in seconds

        Returns:
            Completed Evaluation object

        Raises:
            EvaluationError: If timeout exceeded or evaluation failed
        """
        elapsed = 0.0

        while elapsed < timeout:
            evaluation = await self.get(evaluation_id)

            if evaluation.status == EvaluationStatus.completed:
                return evaluation

            if evaluation.status == EvaluationStatus.failed:
                raise EvaluationError(
                    f"Evaluation failed: {evaluation.error_message}",
                    evaluation_id=str(evaluation_id),
                    reason="failed",
                )

            if evaluation.status == EvaluationStatus.cancelled:
                raise EvaluationError(
                    "Evaluation was cancelled",
                    evaluation_id=str(evaluation_id),
                    reason="cancelled",
                )

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        raise EvaluationError(
            f"Evaluation timed out after {timeout} seconds",
            evaluation_id=str(evaluation_id),
            reason="timeout",
        )

    async def list(
        self,
        agent_id: Optional[UUID] = None,
        status: Optional[EvaluationStatus] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Evaluation], int]:
        """List evaluations with optional filters."""
        response = await self._client.list_evaluations(
            agent_id=agent_id,
            status=status.value if status else None,
            page=page,
            page_size=page_size,
        )

        evaluations = [self._parse_evaluation(e) for e in response.get("items", [])]
        total = response.get("total", len(evaluations))

        return evaluations, total

    def _parse_evaluation(self, data: dict[str, Any]) -> Evaluation:
        """Parse evaluation response to model."""
        from datetime import datetime

        # Parse suites
        suites = [EvaluationSuite(s) for s in data.get("suites", [])]

        # Parse scores
        scores = None
        if data.get("scores"):
            from trustmodel.models.evaluation import EvaluationScores
            scores = EvaluationScores(**data["scores"])

        # Parse suite results
        suite_results = []
        for sr in data.get("suite_results", []):
            from trustmodel.models.evaluation import SuiteResult, TaskResult
            tasks = [TaskResult(**t) for t in sr.get("tasks", [])]
            suite_results.append(SuiteResult(
                suite=EvaluationSuite(sr["suite"]),
                score=sr["score"],
                passed=sr.get("passed", 0),
                failed=sr.get("failed", 0),
                total=sr.get("total", 0),
                tasks=tasks,
                categories=sr.get("categories", {}),
            ))

        return Evaluation(
            id=UUID(data["id"]),
            agent_id=UUID(data["agent_id"]),
            status=EvaluationStatus(data["status"]),
            suites=suites,
            config=data.get("config", {}),
            scores=scores,
            grade=data.get("grade"),
            suite_results=suite_results,
            certified_capabilities=data.get("certified_capabilities", []),
            not_certified=data.get("not_certified", []),
            started_at=datetime.fromisoformat(data["started_at"]),
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            error_message=data.get("error_message"),
            created_at=datetime.fromisoformat(data["created_at"]),
        )


async def evaluate(
    agent: str | UUID,
    suites: Optional[list[str]] = None,
    wait: bool = True,
    timeout: float = 600.0,
    **kwargs: Any,
) -> Evaluation:
    """
    Run an evaluation on an agent.

    This is the main entry point for evaluating agents. By default,
    it waits for the evaluation to complete.

    Args:
        agent: Agent name or ID
        suites: List of suite names (capability, safety, reliability, communication)
        wait: Whether to wait for completion (default: True)
        timeout: Maximum time to wait in seconds
        **kwargs: Additional evaluation configuration

    Returns:
        Evaluation results

    Example:
        from trustmodel import evaluate

        results = await evaluate(
            agent="my-agent",
            suites=["capability", "safety"],
        )

        print(f"Grade: {results.grade}")
        print(f"Overall Score: {results.scores.overall}")
    """
    config = get_config()
    client = EvaluationClient()

    # Resolve agent ID
    if isinstance(agent, str):
        # Try to parse as UUID first
        try:
            agent_id = UUID(agent)
        except ValueError:
            # Look up by name
            api_client = get_client()
            agents_response = await api_client.list_agents()
            agent_id = None
            for a in agents_response.get("items", []):
                if a["name"] == agent:
                    agent_id = UUID(a["id"])
                    break
            if not agent_id:
                raise EvaluationError(f"Agent not found: {agent}")
    else:
        agent_id = agent

    # Start evaluation
    evaluation = await client.start(
        agent_id=agent_id,
        suites=[EvaluationSuite(s) for s in suites] if suites else None,
        config=kwargs,
    )

    if wait:
        evaluation = await client.wait_for_completion(
            evaluation.id,
            timeout=timeout,
        )

    return evaluation
