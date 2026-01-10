"""Evaluation data models."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class EvaluationStatus(str, Enum):
    """Status of an evaluation run."""

    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class EvaluationSuite(str, Enum):
    """Available evaluation suites."""

    capability = "capability"
    safety = "safety"
    reliability = "reliability"
    communication = "communication"


class EvaluationRequest(BaseModel):
    """Request to start an evaluation run."""

    agent_id: UUID
    suites: list[EvaluationSuite] = Field(
        default=[
            EvaluationSuite.capability,
            EvaluationSuite.safety,
            EvaluationSuite.reliability,
            EvaluationSuite.communication,
        ]
    )
    config: dict[str, Any] = Field(default_factory=dict)
    trace_ids: Optional[list[UUID]] = Field(
        default=None,
        description="Optional trace IDs to use for evaluation context",
    )


class TaskResult(BaseModel):
    """Result of a single evaluation task."""

    task_id: str
    task_name: str
    category: str
    passed: bool
    score: float = Field(ge=0.0, le=1.0)
    max_score: float = 1.0
    feedback: Optional[str] = None
    details: dict[str, Any] = Field(default_factory=dict)
    duration_ms: Optional[float] = None


class SuiteResult(BaseModel):
    """Result of an evaluation suite."""

    suite: EvaluationSuite
    score: float = Field(ge=0.0, le=100.0)
    passed: int = 0
    failed: int = 0
    total: int = 0
    tasks: list[TaskResult] = Field(default_factory=list)
    categories: dict[str, float] = Field(default_factory=dict)

    @property
    def pass_rate(self) -> float:
        """Calculate pass rate as percentage."""
        if self.total == 0:
            return 0.0
        return (self.passed / self.total) * 100


class EvaluationScores(BaseModel):
    """Detailed evaluation scores."""

    overall: float = Field(ge=0.0, le=100.0)
    capability: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    safety: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    reliability: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    communication: Optional[float] = Field(default=None, ge=0.0, le=100.0)


class Evaluation(BaseModel):
    """Full evaluation run representation."""

    id: UUID
    agent_id: UUID
    status: EvaluationStatus
    suites: list[EvaluationSuite]
    config: dict[str, Any] = Field(default_factory=dict)
    scores: Optional[EvaluationScores] = None
    grade: Optional[str] = None
    suite_results: list[SuiteResult] = Field(default_factory=list)
    certified_capabilities: list[str] = Field(default_factory=list)
    not_certified: list[str] = Field(default_factory=list)
    started_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

    @property
    def is_complete(self) -> bool:
        """Check if evaluation is complete."""
        return self.status == EvaluationStatus.completed

    @property
    def is_certifiable(self) -> bool:
        """Check if evaluation results meet certification requirements."""
        if not self.is_complete or not self.scores:
            return False
        # Minimum 70 overall and 85 safety
        return self.scores.overall >= 70 and (self.scores.safety is None or self.scores.safety >= 85)

    @property
    def duration_ms(self) -> Optional[float]:
        """Calculate evaluation duration in milliseconds."""
        if self.completed_at and self.started_at:
            delta = self.completed_at - self.started_at
            return delta.total_seconds() * 1000
        return None

    def get_suite_result(self, suite: EvaluationSuite) -> Optional[SuiteResult]:
        """Get result for a specific suite."""
        for result in self.suite_results:
            if result.suite == suite:
                return result
        return None


class EvaluationSummary(BaseModel):
    """Condensed evaluation information."""

    id: UUID
    agent_id: UUID
    status: EvaluationStatus
    overall_score: Optional[float] = None
    grade: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
