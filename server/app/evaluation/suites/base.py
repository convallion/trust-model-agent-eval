"""Base evaluation suite class."""

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID

import structlog

from app.evaluation.executor import TaskExecutor

logger = structlog.get_logger()


class EvaluationSuite(ABC):
    """
    Base class for evaluation suites.

    Each suite tests a specific aspect of agent trustworthiness:
    - Capability: What can the agent do?
    - Safety: Is the agent safe to deploy?
    - Reliability: Will the agent work consistently?
    - Communication: Can the agent safely collaborate with others?
    """

    name: str = "base"
    description: str = "Base evaluation suite"

    def __init__(
        self,
        agent_id: UUID,
        executor: TaskExecutor,
        config: Dict[str, Any],
    ) -> None:
        """
        Initialize the evaluation suite.

        Args:
            agent_id: ID of the agent being evaluated
            executor: Task executor for running tests
            config: Evaluation configuration
        """
        self.agent_id = agent_id
        self.executor = executor
        self.config = config
        self.trials_per_task = config.get("trials_per_task", 3)

    @abstractmethod
    async def run(
        self,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, Any]:
        """
        Run all tests in the suite.

        Args:
            progress_callback: Callback for progress updates

        Returns:
            Dictionary with:
            - score: Overall suite score (0-100)
            - tests: Dict of test results
        """
        pass

    def calculate_score(self, test_results: Dict[str, Any]) -> float:
        """
        Calculate overall suite score from test results.

        Default implementation: average of all test scores.
        Override in subclasses for custom weighting.
        """
        if not test_results:
            return 0.0

        total_score = sum(
            test.get("score", 0) for test in test_results.values()
        )
        return round(total_score / len(test_results), 2)

    async def run_test(
        self,
        test_name: str,
        test_fn: Callable,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Run a single test with standard result formatting.

        Args:
            test_name: Name of the test
            test_fn: Test function to execute
            **kwargs: Arguments to pass to test function

        Returns:
            Test result dictionary
        """
        logger.info(f"Running test: {test_name}")

        try:
            result = await test_fn(**kwargs)

            return {
                "score": result.get("score", 0),
                "passed": result.get("passed", 0),
                "failed": result.get("failed", 0),
                "details": result.get("details", []),
            }
        except Exception as e:
            logger.error(f"Test {test_name} failed", error=str(e))
            return {
                "score": 0,
                "error": str(e),
                "passed": 0,
                "failed": 1,
            }
