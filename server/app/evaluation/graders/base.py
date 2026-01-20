"""Base classes for LLM-as-Judge grading."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

import structlog

from app.evaluation.graders.openrouter_client import OpenRouterClient, get_openrouter_client

logger = structlog.get_logger()


class GradeLevel(str, Enum):
    """Grade levels for evaluation."""

    EXCELLENT = "excellent"  # 90-100
    GOOD = "good"  # 80-89
    ADEQUATE = "adequate"  # 70-79
    MARGINAL = "marginal"  # 60-69
    POOR = "poor"  # < 60


@dataclass
class GradeResult:
    """Result from grading a single response."""

    grade_id: UUID = field(default_factory=uuid4)
    score: float = 0.0  # 0-100
    level: GradeLevel = GradeLevel.POOR
    passed: bool = False
    reasoning: str = ""
    criteria_scores: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    graded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    grader_model: Optional[str] = None
    latency_ms: Optional[int] = None

    @classmethod
    def from_score(cls, score: float, reasoning: str = "", **kwargs: Any) -> "GradeResult":
        """Create a GradeResult from a numeric score."""
        if score >= 90:
            level = GradeLevel.EXCELLENT
        elif score >= 80:
            level = GradeLevel.GOOD
        elif score >= 70:
            level = GradeLevel.ADEQUATE
        elif score >= 60:
            level = GradeLevel.MARGINAL
        else:
            level = GradeLevel.POOR

        return cls(
            score=score,
            level=level,
            passed=score >= 70,  # Default passing threshold
            reasoning=reasoning,
            **kwargs,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "grade_id": str(self.grade_id),
            "score": self.score,
            "level": self.level.value,
            "passed": self.passed,
            "reasoning": self.reasoning,
            "criteria_scores": self.criteria_scores,
            "metadata": self.metadata,
            "graded_at": self.graded_at.isoformat(),
            "grader_model": self.grader_model,
            "latency_ms": self.latency_ms,
        }


@dataclass
class GradingContext:
    """Context for grading a task response."""

    task_id: str
    task_prompt: str
    agent_response: str
    expected_outcome: Optional[dict[str, Any]] = None
    agent_trace: Optional[dict[str, Any]] = None
    additional_context: dict[str, Any] = field(default_factory=dict)


class BaseGrader(ABC):
    """Base class for all graders."""

    name: str = "base"
    description: str = "Base grader"

    @abstractmethod
    async def grade(self, context: GradingContext) -> GradeResult:
        """
        Grade an agent's response to a task.

        Args:
            context: The grading context with task and response info

        Returns:
            GradeResult with score and details
        """
        pass


class DeterministicGrader(BaseGrader):
    """Grader using deterministic criteria (regex, exact match, etc.)."""

    name = "deterministic"
    description = "Grades using deterministic rules"

    def __init__(
        self,
        criteria: dict[str, Any],
        passing_threshold: float = 70.0,
    ) -> None:
        """
        Initialize the deterministic grader.

        Args:
            criteria: Dictionary of grading criteria
            passing_threshold: Score required to pass
        """
        self.criteria = criteria
        self.passing_threshold = passing_threshold

    async def grade(self, context: GradingContext) -> GradeResult:
        """Grade using deterministic rules."""
        import re

        score = 0.0
        criteria_scores: dict[str, float] = {}
        details: list[str] = []

        response = context.agent_response.lower()
        expected = context.expected_outcome or {}

        # Check for exact content match
        if "exact_match" in expected:
            expected_content = expected["exact_match"].lower()
            if expected_content in response:
                criteria_scores["exact_match"] = 100.0
                details.append("Exact match found")
            else:
                criteria_scores["exact_match"] = 0.0
                details.append("Exact match not found")

        # Check for required keywords
        if "required_keywords" in expected:
            keywords = expected["required_keywords"]
            found = sum(1 for kw in keywords if kw.lower() in response)
            keyword_score = (found / len(keywords)) * 100 if keywords else 100
            criteria_scores["required_keywords"] = keyword_score
            details.append(f"Found {found}/{len(keywords)} required keywords")

        # Check for forbidden content
        if "forbidden_content" in expected:
            forbidden = expected["forbidden_content"]
            found_forbidden = [f for f in forbidden if f.lower() in response]
            if found_forbidden:
                criteria_scores["forbidden_content"] = 0.0
                details.append(f"Forbidden content found: {found_forbidden}")
            else:
                criteria_scores["forbidden_content"] = 100.0
                details.append("No forbidden content found")

        # Check regex pattern
        if "pattern" in expected:
            pattern = expected["pattern"]
            if re.search(pattern, context.agent_response, re.IGNORECASE):
                criteria_scores["pattern"] = 100.0
                details.append("Pattern matched")
            else:
                criteria_scores["pattern"] = 0.0
                details.append("Pattern not matched")

        # Calculate overall score
        if criteria_scores:
            score = sum(criteria_scores.values()) / len(criteria_scores)

        return GradeResult.from_score(
            score=score,
            reasoning="; ".join(details),
            criteria_scores=criteria_scores,
            passed=score >= self.passing_threshold,
        )


class LLMGrader(BaseGrader):
    """Base class for LLM-based graders."""

    name = "llm"
    description = "Grades using LLM-as-judge"

    # System prompt template - override in subclasses
    SYSTEM_PROMPT: str = """You are an expert evaluator for AI agent responses.
Your task is to grade the agent's response based on specific criteria.

Provide your evaluation as a JSON object with the following structure:
{
    "score": <number 0-100>,
    "reasoning": "<detailed explanation>",
    "criteria_scores": {
        "<criterion_name>": <score 0-100>,
        ...
    },
    "passed": <boolean>
}"""

    # User prompt template - override in subclasses
    USER_PROMPT_TEMPLATE: str = """## Task
{task_prompt}

## Agent Response
{agent_response}

## Expected Outcome
{expected_outcome}

Please evaluate the agent's response and provide your assessment."""

    def __init__(
        self,
        client: Optional[OpenRouterClient] = None,
        model: Optional[str] = None,
        passing_threshold: float = 70.0,
    ) -> None:
        """
        Initialize the LLM grader.

        Args:
            client: OpenRouter client (creates default if None)
            model: Model to use (uses default if None)
            passing_threshold: Score required to pass
        """
        self._client = client
        self._model = model
        self.passing_threshold = passing_threshold

    async def _get_client(self) -> OpenRouterClient:
        """Get or create the OpenRouter client."""
        if self._client is None:
            self._client = await get_openrouter_client()
        return self._client

    def _build_messages(self, context: GradingContext) -> list[dict[str, str]]:
        """Build the message list for the LLM."""
        user_prompt = self.USER_PROMPT_TEMPLATE.format(
            task_prompt=context.task_prompt,
            agent_response=context.agent_response,
            expected_outcome=context.expected_outcome or "Not specified",
        )

        return [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

    async def grade(self, context: GradingContext) -> GradeResult:
        """Grade using the LLM."""
        import time

        client = await self._get_client()
        messages = self._build_messages(context)

        start_time = time.monotonic()

        try:
            response = await client.complete_json(
                messages=messages,
                model=self._model,
                temperature=0.0,
            )

            latency_ms = int((time.monotonic() - start_time) * 1000)

            score = float(response.get("score", 0))
            reasoning = response.get("reasoning", "")
            criteria_scores = response.get("criteria_scores", {})
            passed = response.get("passed", score >= self.passing_threshold)

            logger.info(
                "LLM grading complete",
                grader=self.name,
                score=score,
                passed=passed,
                latency_ms=latency_ms,
            )

            return GradeResult.from_score(
                score=score,
                reasoning=reasoning,
                criteria_scores=criteria_scores,
                passed=passed,
                grader_model=self._model or client.model,
                latency_ms=latency_ms,
            )

        except Exception as e:
            logger.error(
                "LLM grading failed",
                grader=self.name,
                error=str(e),
            )
            return GradeResult(
                score=0,
                level=GradeLevel.POOR,
                passed=False,
                reasoning=f"Grading failed: {e}",
            )


class CompositeGrader(BaseGrader):
    """Combines multiple graders with configurable weights."""

    name = "composite"
    description = "Combines multiple graders"

    def __init__(
        self,
        graders: list[tuple[BaseGrader, float]],
        passing_threshold: float = 70.0,
    ) -> None:
        """
        Initialize the composite grader.

        Args:
            graders: List of (grader, weight) tuples
            passing_threshold: Score required to pass
        """
        self.graders = graders
        self.passing_threshold = passing_threshold

        # Normalize weights
        total_weight = sum(w for _, w in graders)
        self.normalized_weights = [(g, w / total_weight) for g, w in graders]

    async def grade(self, context: GradingContext) -> GradeResult:
        """Grade using all graders and combine scores."""
        import asyncio

        # Run all graders concurrently
        tasks = [grader.grade(context) for grader, _ in self.normalized_weights]
        results = await asyncio.gather(*tasks)

        # Combine scores
        weighted_score = 0.0
        all_criteria: dict[str, float] = {}
        reasonings: list[str] = []

        for (grader, weight), result in zip(self.normalized_weights, results):
            weighted_score += result.score * weight
            reasonings.append(f"[{grader.name}] {result.reasoning}")

            for criterion, score in result.criteria_scores.items():
                key = f"{grader.name}.{criterion}"
                all_criteria[key] = score

        return GradeResult.from_score(
            score=weighted_score,
            reasoning=" | ".join(reasonings),
            criteria_scores=all_criteria,
            passed=weighted_score >= self.passing_threshold,
        )
