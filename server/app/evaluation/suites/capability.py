"""Capability evaluation suite - tests what the agent can do."""

from typing import Any, Callable, Dict, Optional

import structlog

from app.evaluation.agent_executor import BaseAgentExecutor, ExecutionResult
from app.evaluation.graders import (
    GradingContext,
    OpenRouterClient,
    ReasoningQualityGrader,
    TaskCompletionGrader,
    ToolProficiencyGrader,
    EfficiencyGrader,
    get_openrouter_client,
)
from app.evaluation.metrics import TraceAnalyzer, get_trace_analyzer
from app.evaluation.scoring import CapabilityScorer, TestResult
from app.evaluation.suites.base import EvaluationSuite
from app.evaluation.tasks import get_capability_tasks, TaskDefinition

logger = structlog.get_logger()


class CapabilitySuite(EvaluationSuite):
    """
    Capability evaluation suite.

    Tests:
    - Task completion: Can the agent complete assigned tasks?
    - Tool proficiency: Does the agent use tools correctly?
    - Reasoning quality: Are decisions well-founded?
    - Efficiency: Minimal steps, tokens, cost?
    """

    name = "capability"
    description = "Evaluates agent capabilities and task completion"

    # Test weights for score calculation
    WEIGHTS = {
        "task_completion": 0.35,
        "tool_proficiency": 0.25,
        "reasoning_quality": 0.25,
        "efficiency": 0.15,
    }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._openrouter_client: Optional[OpenRouterClient] = None
        self._graders: Dict[str, Any] = {}
        self._task_bank = get_capability_tasks()
        self._trace_analyzer = get_trace_analyzer()
        self._scorer = CapabilityScorer(weights=self.WEIGHTS)

    async def _get_openrouter_client(self) -> OpenRouterClient:
        """Get or create OpenRouter client."""
        if self._openrouter_client is None:
            self._openrouter_client = await get_openrouter_client()
        return self._openrouter_client

    async def _get_graders(self) -> Dict[str, Any]:
        """Initialize graders lazily."""
        if not self._graders:
            client = await self._get_openrouter_client()
            self._graders = {
                "task_completion": TaskCompletionGrader(client=client),
                "tool_proficiency": ToolProficiencyGrader(client=client),
                "reasoning_quality": ReasoningQualityGrader(client=client),
                "efficiency": EfficiencyGrader(client=client),
            }
        return self._graders

    async def run(
        self,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, Any]:
        """Run all capability tests."""
        results: Dict[str, Any] = {"tests": {}}

        # Task completion test
        if progress_callback:
            progress_callback("task_completion")
        results["tests"]["task_completion"] = await self.run_test(
            "task_completion",
            self._test_task_completion,
        )

        # Tool proficiency test
        if progress_callback:
            progress_callback("tool_proficiency")
        results["tests"]["tool_proficiency"] = await self.run_test(
            "tool_proficiency",
            self._test_tool_proficiency,
        )

        # Reasoning quality test
        if progress_callback:
            progress_callback("reasoning_quality")
        results["tests"]["reasoning_quality"] = await self.run_test(
            "reasoning_quality",
            self._test_reasoning_quality,
        )

        # Efficiency test
        if progress_callback:
            progress_callback("efficiency")
        results["tests"]["efficiency"] = await self.run_test(
            "efficiency",
            self._test_efficiency,
        )

        # Calculate weighted score
        results["score"] = self._calculate_weighted_score(results["tests"])

        return results

    def _calculate_weighted_score(self, test_results: Dict[str, Any]) -> float:
        """Calculate weighted score from test results."""
        total_weight = 0.0
        weighted_sum = 0.0

        for test_name, weight in self.WEIGHTS.items():
            if test_name in test_results:
                score = test_results[test_name].get("score", 0)
                weighted_sum += score * weight
                total_weight += weight

        if total_weight == 0:
            return 0.0

        return round(weighted_sum / total_weight, 2)

    async def _test_task_completion(self) -> Dict[str, Any]:
        """
        Test task completion capability.

        Runs a set of tasks and measures completion rate using LLM grading.
        """
        graders = await self._get_graders()
        task_grader = graders["task_completion"]

        # Get task completion tasks
        tasks = self._task_bank.get_by_tag("coding")
        if not tasks:
            # Fallback to all tasks if no specific tag
            tasks = self._task_bank.sample(10, category="task_completion")

        test_results: list[TestResult] = []

        for task in tasks[:10]:  # Limit to 10 tasks
            # Execute task against agent
            execution_result = await self._execute_task(task)

            if execution_result.success:
                # Grade the response
                context = GradingContext(
                    task_id=task.id,
                    task_prompt=task.prompt,
                    agent_response=execution_result.response,
                    expected_outcome=task.expected_outcome.to_dict(),
                    agent_trace=execution_result.trace_data,
                )

                grade_result = await task_grader.grade(context)

                test_results.append(TestResult(
                    test_id=task.id,
                    test_name=task.name,
                    passed=grade_result.passed,
                    score=grade_result.score,
                    grade_result=grade_result,
                ))
            else:
                test_results.append(TestResult(
                    test_id=task.id,
                    test_name=task.name,
                    passed=False,
                    score=0,
                    error=execution_result.error,
                ))

        # Calculate results
        passed = sum(1 for r in test_results if r.passed)
        failed = len(test_results) - passed
        avg_score = sum(r.score for r in test_results) / len(test_results) if test_results else 0

        return {
            "score": round(avg_score, 2),
            "passed": passed,
            "failed": failed,
            "details": [r.to_dict() for r in test_results],
        }

    async def _test_tool_proficiency(self) -> Dict[str, Any]:
        """
        Test tool usage proficiency.

        Measures correct tool selection, parameter accuracy, and error handling.
        """
        graders = await self._get_graders()
        tool_grader = graders["tool_proficiency"]

        # Get tasks that require tool usage
        tasks = self._task_bank.get_by_tag("tool_usage")
        if not tasks:
            tasks = self._task_bank.sample(5)

        test_results: list[TestResult] = []

        for task in tasks[:5]:
            execution_result = await self._execute_task(task)

            if execution_result.success and execution_result.trace_data:
                context = GradingContext(
                    task_id=task.id,
                    task_prompt=task.prompt,
                    agent_response=execution_result.response,
                    agent_trace=execution_result.trace_data,
                    additional_context={
                        "available_tools": task.metadata.get("available_tools", []),
                    },
                )

                grade_result = await tool_grader.grade(context)

                test_results.append(TestResult(
                    test_id=task.id,
                    test_name=task.name,
                    passed=grade_result.passed,
                    score=grade_result.score,
                    grade_result=grade_result,
                ))
            else:
                # Without trace data, use default scoring
                test_results.append(TestResult(
                    test_id=task.id,
                    test_name=task.name,
                    passed=execution_result.success,
                    score=70 if execution_result.success else 0,
                ))

        passed = sum(1 for r in test_results if r.passed)
        failed = len(test_results) - passed
        avg_score = sum(r.score for r in test_results) / len(test_results) if test_results else 0

        return {
            "score": round(avg_score, 2),
            "passed": passed,
            "failed": failed,
            "details": [r.to_dict() for r in test_results],
        }

    async def _test_reasoning_quality(self) -> Dict[str, Any]:
        """
        Test reasoning quality.

        Uses LLM-as-judge to evaluate decision quality.
        """
        graders = await self._get_graders()
        reasoning_grader = graders["reasoning_quality"]

        # Get reasoning-focused tasks
        tasks = self._task_bank.get_by_tag("reasoning")
        if not tasks:
            tasks = self._task_bank.sample(5, category="reasoning")

        test_results: list[TestResult] = []

        for task in tasks[:5]:
            execution_result = await self._execute_task(task)

            if execution_result.success:
                context = GradingContext(
                    task_id=task.id,
                    task_prompt=task.prompt,
                    agent_response=execution_result.response,
                    expected_outcome=task.expected_outcome.to_dict(),
                )

                grade_result = await reasoning_grader.grade(context)

                test_results.append(TestResult(
                    test_id=task.id,
                    test_name=task.name,
                    passed=grade_result.passed,
                    score=grade_result.score,
                    grade_result=grade_result,
                ))
            else:
                test_results.append(TestResult(
                    test_id=task.id,
                    test_name=task.name,
                    passed=False,
                    score=0,
                    error=execution_result.error,
                ))

        passed = sum(1 for r in test_results if r.passed)
        failed = len(test_results) - passed
        avg_score = sum(r.score for r in test_results) / len(test_results) if test_results else 0

        return {
            "score": round(avg_score, 2),
            "passed": passed,
            "failed": failed,
            "details": [r.to_dict() for r in test_results],
        }

    async def _test_efficiency(self) -> Dict[str, Any]:
        """
        Test efficiency metrics.

        Measures tokens, time, and tool calls per task.
        """
        graders = await self._get_graders()
        efficiency_grader = graders["efficiency"]

        # Run a few tasks and analyze their traces
        tasks = self._task_bank.sample(5)
        test_results: list[TestResult] = []
        all_metrics = []

        for task in tasks:
            execution_result = await self._execute_task(task)

            if execution_result.success and execution_result.trace_data:
                # Analyze trace for efficiency metrics
                trace_metrics = self._trace_analyzer.analyze_trace(execution_result.trace_data)
                all_metrics.append(trace_metrics)

                context = GradingContext(
                    task_id=task.id,
                    task_prompt=task.prompt,
                    agent_response=execution_result.response,
                    agent_trace=execution_result.trace_data,
                )

                grade_result = await efficiency_grader.grade(context)

                test_results.append(TestResult(
                    test_id=task.id,
                    test_name=task.name,
                    passed=grade_result.passed,
                    score=grade_result.score,
                    grade_result=grade_result,
                    trace_metrics=trace_metrics,
                ))
            else:
                # Calculate efficiency from execution result directly
                efficiency_score = 70 if execution_result.duration_ms < 30000 else 50
                test_results.append(TestResult(
                    test_id=task.id,
                    test_name=task.name,
                    passed=efficiency_score >= 70,
                    score=efficiency_score,
                ))

        passed = sum(1 for r in test_results if r.passed)
        failed = len(test_results) - passed
        avg_score = sum(r.score for r in test_results) / len(test_results) if test_results else 0

        # Aggregate efficiency metrics
        avg_metrics = {}
        if all_metrics:
            avg_metrics = {
                "avg_tokens_per_task": sum(m.total_tokens for m in all_metrics) / len(all_metrics),
                "avg_time_per_task_ms": sum(m.total_duration_ms for m in all_metrics) / len(all_metrics),
                "avg_tool_calls_per_task": sum(m.total_tool_calls for m in all_metrics) / len(all_metrics),
            }

        return {
            "score": round(avg_score, 2),
            "passed": passed,
            "failed": failed,
            "details": [r.to_dict() for r in test_results],
            "aggregate_metrics": avg_metrics,
        }

    async def _execute_task(self, task: TaskDefinition) -> ExecutionResult:
        """Execute a task against the agent."""
        # Use the executor from the base class
        return await self.executor.execute_task(
            task.id,
            lambda: self._run_agent_task(task),
        )

    async def _run_agent_task(self, task: TaskDefinition) -> ExecutionResult:
        """
        Run a task against the agent.

        This method should be overridden or configured to use the actual
        agent executor (LangSmith, HTTP, etc.)
        """
        from app.evaluation.agent_executor import MockAgentExecutor

        # Default to mock executor if no real executor configured
        executor = getattr(self, "_agent_executor", None)
        if executor is None:
            executor = MockAgentExecutor(self.agent_id)
            self._agent_executor = executor

        return await executor.execute(task)
