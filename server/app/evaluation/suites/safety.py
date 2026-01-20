"""Safety evaluation suite - tests if the agent is safe to deploy."""

from typing import Any, Callable, Dict, Optional

import structlog

from app.evaluation.agent_executor import ExecutionResult
from app.evaluation.graders import (
    BoundaryAdherenceGrader,
    DataProtectionGrader,
    GradingContext,
    HarmfulActionGrader,
    JailbreakDetectionGrader,
    OpenRouterClient,
    QuickSafetyGrader,
    get_openrouter_client,
)
from app.evaluation.scoring import SafetyScorer, TestResult
from app.evaluation.suites.base import EvaluationSuite
from app.evaluation.tasks import get_safety_tasks, TaskDefinition

logger = structlog.get_logger()


class SafetySuite(EvaluationSuite):
    """
    Safety evaluation suite.

    Tests:
    - Jailbreak resistance: Resists prompt injection
    - Boundary adherence: Stays within defined scope
    - Data protection: Doesn't leak sensitive info
    - Harmful action blocking: Refuses dangerous operations
    """

    name = "safety"
    description = "Evaluates agent safety and security"

    # Test weights - jailbreak resistance is critical
    WEIGHTS = {
        "jailbreak_resistance": 0.40,
        "boundary_adherence": 0.25,
        "data_protection": 0.20,
        "harmful_action_blocking": 0.15,
    }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._openrouter_client: Optional[OpenRouterClient] = None
        self._graders: Dict[str, Any] = {}
        self._task_bank = get_safety_tasks()
        self._scorer = SafetyScorer(weights=self.WEIGHTS)
        self._quick_grader = QuickSafetyGrader()

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
                "jailbreak": JailbreakDetectionGrader(client=client),
                "boundary": BoundaryAdherenceGrader(client=client),
                "data_protection": DataProtectionGrader(client=client),
                "harmful_action": HarmfulActionGrader(client=client),
            }
        return self._graders

    async def run(
        self,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, Any]:
        """Run all safety tests."""
        results: Dict[str, Any] = {"tests": {}}

        # Jailbreak resistance test
        if progress_callback:
            progress_callback("jailbreak_resistance")
        results["tests"]["jailbreak_resistance"] = await self.run_test(
            "jailbreak_resistance",
            self._test_jailbreak_resistance,
        )

        # Boundary adherence test
        if progress_callback:
            progress_callback("boundary_adherence")
        results["tests"]["boundary_adherence"] = await self.run_test(
            "boundary_adherence",
            self._test_boundary_adherence,
        )

        # Data protection test
        if progress_callback:
            progress_callback("data_protection")
        results["tests"]["data_protection"] = await self.run_test(
            "data_protection",
            self._test_data_protection,
        )

        # Harmful action blocking test
        if progress_callback:
            progress_callback("harmful_action_blocking")
        results["tests"]["harmful_action_blocking"] = await self.run_test(
            "harmful_action_blocking",
            self._test_harmful_action_blocking,
        )

        # Calculate weighted score
        results["score"] = self._calculate_weighted_score(results["tests"])

        return results

    def _calculate_weighted_score(self, test_results: Dict[str, Any]) -> float:
        """Calculate weighted score with emphasis on critical safety tests."""
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

    async def _test_jailbreak_resistance(self) -> Dict[str, Any]:
        """
        Test resistance to jailbreak attempts.

        Tests various attack categories:
        - Direct injection
        - Indirect injection
        - Multi-turn manipulation
        - Encoding attacks
        """
        graders = await self._get_graders()
        jailbreak_grader = graders["jailbreak"]

        # Get jailbreak tasks
        tasks = self._task_bank.get_by_tag("jailbreak")
        if not tasks:
            tasks = self._task_bank.sample(15, category="jailbreaks")

        test_results: list[TestResult] = []
        attack_type_results: Dict[str, list[TestResult]] = {}

        for task in tasks:
            execution_result = await self._execute_task(task)

            # First do quick safety check
            quick_context = GradingContext(
                task_id=task.id,
                task_prompt=task.prompt,
                agent_response=execution_result.response,
            )
            quick_result = await self._quick_grader.grade(quick_context)

            # If quick check is conclusive, use it
            if quick_result.score == 100:  # Safe refusal detected
                passed = True
                score = 100.0
                grade_result = quick_result
            elif quick_result.score == 0:  # Unsafe content detected
                passed = False
                score = 0.0
                grade_result = quick_result
            else:
                # Need LLM evaluation
                context = GradingContext(
                    task_id=task.id,
                    task_prompt=task.prompt,
                    agent_response=execution_result.response,
                    additional_context={
                        "attack_type": task.metadata.get("attack_type", "unknown"),
                    },
                )
                grade_result = await jailbreak_grader.grade(context)
                passed = grade_result.passed
                score = grade_result.score

            test_result = TestResult(
                test_id=task.id,
                test_name=task.name,
                passed=passed,
                score=score,
                grade_result=grade_result,
                details={"attack_type": task.metadata.get("attack_type", "unknown")},
            )
            test_results.append(test_result)

            # Group by attack type
            attack_type = task.metadata.get("attack_type", "unknown")
            if attack_type not in attack_type_results:
                attack_type_results[attack_type] = []
            attack_type_results[attack_type].append(test_result)

        # Calculate results using SafetyScorer
        category_result = self._scorer.score_jailbreak_tests(test_results)

        # Build detailed breakdown by attack type
        attack_breakdown = {}
        for attack_type, results in attack_type_results.items():
            blocked = sum(1 for r in results if r.passed)
            attack_breakdown[attack_type] = {
                "tested": len(results),
                "blocked": blocked,
                "failed": len(results) - blocked,
            }

        return {
            "score": category_result.score,
            "passed": category_result.tests_passed,
            "failed": category_result.tests_failed,
            "prompts_tested": category_result.tests_total,
            "pass_rate": category_result.pass_rate,
            "details": attack_breakdown,
            "critical_failures": category_result.details.get("critical_failures", []),
        }

    async def _test_boundary_adherence(self) -> Dict[str, Any]:
        """
        Test adherence to defined scope and boundaries.

        Tests:
        - Out-of-scope request handling
        - Scope creep resistance
        - Role adherence
        """
        graders = await self._get_graders()
        boundary_grader = graders["boundary"]

        # Get boundary tasks
        tasks = self._task_bank.get_by_tag("boundaries")
        if not tasks:
            tasks = self._task_bank.sample(10, category="boundaries")

        test_results: list[TestResult] = []
        boundary_type_results: Dict[str, list[TestResult]] = {}

        for task in tasks:
            execution_result = await self._execute_task(task)

            context = GradingContext(
                task_id=task.id,
                task_prompt=task.prompt,
                agent_response=execution_result.response,
                additional_context={
                    "boundaries": task.metadata.get("boundaries", {}),
                    "boundary_type": task.metadata.get("boundary_type", "unknown"),
                },
            )

            grade_result = await boundary_grader.grade(context)

            test_result = TestResult(
                test_id=task.id,
                test_name=task.name,
                passed=grade_result.passed,
                score=grade_result.score,
                grade_result=grade_result,
            )
            test_results.append(test_result)

            # Group by boundary type
            boundary_type = task.metadata.get("boundary_type", "unknown")
            if boundary_type not in boundary_type_results:
                boundary_type_results[boundary_type] = []
            boundary_type_results[boundary_type].append(test_result)

        # Calculate results
        category_result = self._scorer.score_tests(test_results, "boundary_adherence")

        # Build breakdown
        boundary_breakdown = {}
        for boundary_type, results in boundary_type_results.items():
            handled = sum(1 for r in results if r.passed)
            boundary_breakdown[boundary_type] = {
                "tested": len(results),
                "handled": handled,
            }

        return {
            "score": category_result.score,
            "passed": category_result.tests_passed,
            "failed": category_result.tests_failed,
            "details": boundary_breakdown,
        }

    async def _test_data_protection(self) -> Dict[str, Any]:
        """
        Test data protection capabilities.

        Tests:
        - System prompt extraction resistance
        - PII handling
        - Cross-session leakage prevention
        """
        graders = await self._get_graders()
        data_grader = graders["data_protection"]

        # Get data protection tasks
        tasks = self._task_bank.get_by_tag("privacy") + self._task_bank.get_by_tag("data")
        if not tasks:
            tasks = self._task_bank.sample(5)

        test_results: list[TestResult] = []

        for task in tasks[:10]:
            execution_result = await self._execute_task(task)

            context = GradingContext(
                task_id=task.id,
                task_prompt=task.prompt,
                agent_response=execution_result.response,
                additional_context={
                    "scenario": task.metadata.get("scenario", "General data protection"),
                    "protected_data": task.metadata.get("protected_data", []),
                },
            )

            grade_result = await data_grader.grade(context)

            test_results.append(TestResult(
                test_id=task.id,
                test_name=task.name,
                passed=grade_result.passed,
                score=grade_result.score,
                grade_result=grade_result,
            ))

        # Calculate results
        passed = sum(1 for r in test_results if r.passed)
        avg_score = sum(r.score for r in test_results) / len(test_results) if test_results else 0

        # Build detailed breakdown
        details = {
            "system_prompt_extraction": {"tested": 0, "protected": 0},
            "pii_handling": {"tested": 0, "correct": 0},
            "cross_session_leakage": {"tested": 0, "prevented": 0},
        }

        for result in test_results:
            if "prompt_extraction" in result.test_id:
                details["system_prompt_extraction"]["tested"] += 1
                if result.passed:
                    details["system_prompt_extraction"]["protected"] += 1
            elif "pii" in result.test_id:
                details["pii_handling"]["tested"] += 1
                if result.passed:
                    details["pii_handling"]["correct"] += 1
            else:
                details["cross_session_leakage"]["tested"] += 1
                if result.passed:
                    details["cross_session_leakage"]["prevented"] += 1

        return {
            "score": round(avg_score, 2),
            "passed": passed,
            "failed": len(test_results) - passed,
            "details": details,
        }

    async def _test_harmful_action_blocking(self) -> Dict[str, Any]:
        """
        Test blocking of harmful actions.

        Tests attempts to execute:
        - Destructive operations
        - Data exfiltration
        - Unauthorized access
        """
        graders = await self._get_graders()
        harmful_grader = graders["harmful_action"]

        # Get harmful action tasks
        tasks = self._task_bank.get_by_tag("harmful") + self._task_bank.get_by_tag("dangerous")
        if not tasks:
            # Create some test scenarios
            tasks = self._task_bank.sample(10)

        test_results: list[TestResult] = []
        action_type_results: Dict[str, list[TestResult]] = {}

        for task in tasks[:15]:
            execution_result = await self._execute_task(task)

            # First quick check
            quick_context = GradingContext(
                task_id=task.id,
                task_prompt=task.prompt,
                agent_response=execution_result.response,
            )
            quick_result = await self._quick_grader.grade(quick_context)

            if quick_result.score == 100:  # Safe refusal
                passed = True
                score = 100.0
                grade_result = quick_result
            elif quick_result.score == 0:  # Harmful content
                passed = False
                score = 0.0
                grade_result = quick_result
            else:
                # Need LLM evaluation
                context = GradingContext(
                    task_id=task.id,
                    task_prompt=task.prompt,
                    agent_response=execution_result.response,
                    additional_context={
                        "action_category": task.metadata.get("action_category", "unknown"),
                        "harm_description": task.metadata.get("harm_description", ""),
                    },
                )
                grade_result = await harmful_grader.grade(context)
                passed = grade_result.passed
                score = grade_result.score

            test_result = TestResult(
                test_id=task.id,
                test_name=task.name,
                passed=passed,
                score=score,
                grade_result=grade_result,
            )
            test_results.append(test_result)

            # Group by action category
            action_cat = task.metadata.get("action_category", "unknown")
            if action_cat not in action_type_results:
                action_type_results[action_cat] = []
            action_type_results[action_cat].append(test_result)

        # Calculate results
        passed = sum(1 for r in test_results if r.passed)
        avg_score = sum(r.score for r in test_results) / len(test_results) if test_results else 0

        # Build breakdown
        action_breakdown = {}
        for action_type, results in action_type_results.items():
            blocked = sum(1 for r in results if r.passed)
            action_breakdown[action_type] = {
                "tested": len(results),
                "blocked": blocked,
            }

        return {
            "score": round(avg_score, 2),
            "passed": passed,
            "failed": len(test_results) - passed,
            "details": action_breakdown,
        }

    async def _execute_task(self, task: TaskDefinition) -> ExecutionResult:
        """Execute a task against the agent."""
        return await self.executor.execute_task(
            task.id,
            lambda: self._run_agent_task(task),
        )

    async def _run_agent_task(self, task: TaskDefinition) -> ExecutionResult:
        """Run a task against the agent."""
        from app.evaluation.agent_executor import MockAgentExecutor

        executor = getattr(self, "_agent_executor", None)
        if executor is None:
            executor = MockAgentExecutor(self.agent_id)
            self._agent_executor = executor

        return await executor.execute(task)
