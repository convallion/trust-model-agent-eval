"""Evaluation schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.evaluation import EvaluationGrade
from app.models.evaluation import EvaluationStatus as EvalStatus


class EvaluationStatus(BaseModel):
    """Evaluation status information."""

    status: EvalStatus
    progress_percent: int
    current_suite: Optional[str]
    current_test: Optional[str]


class EvaluationConfig(BaseModel):
    """Configuration for evaluation run."""

    trials_per_task: int = Field(default=3, ge=1, le=10)
    parallel: int = Field(default=5, ge=1, le=20)
    timeout_minutes: int = Field(default=60, ge=1, le=480)


class EvaluationRequest(BaseModel):
    """Request to start an evaluation."""

    agent_id: UUID
    suites: List[str] = Field(
        default=["capability", "safety", "reliability", "communication"],
        description="Evaluation suites to run",
    )
    config: EvaluationConfig = Field(default_factory=EvaluationConfig)


class EvaluationSuiteResult(BaseModel):
    """Results for a single evaluation suite."""

    suite: str
    score: float
    passed: int
    total: int
    tests: Dict[str, Any]


# Alias for backwards compatibility
SuiteResult = EvaluationSuiteResult


class EvaluationResponse(BaseModel):
    """Evaluation run response."""

    id: UUID
    agent_id: UUID
    status: EvalStatus
    suites: List[str]
    config: Dict[str, Any]

    # Timing
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_seconds: Optional[int]
    created_at: datetime

    # Progress (for running evaluations)
    progress_percent: int
    current_suite: Optional[str]
    current_test: Optional[str]

    # Results (for completed evaluations)
    overall_score: Optional[float]
    grade: Optional[EvaluationGrade]
    certificate_eligible: bool
    capability_score: Optional[float]
    safety_score: Optional[float]
    reliability_score: Optional[float]
    communication_score: Optional[float]
    results: Dict[str, Any]

    # Error (for failed evaluations)
    error_message: Optional[str]

    model_config = {"from_attributes": True}


class EvaluationListResponse(BaseModel):
    """Paginated list of evaluations."""

    items: List[EvaluationResponse]
    total: int
    page: int
    page_size: int
    pages: int


class EvaluationSummary(BaseModel):
    """Summary of an agent's evaluation history."""

    total_evaluations: int
    completed_evaluations: int
    passed_evaluations: int
    average_score: Optional[float]
    best_score: Optional[float]
    best_grade: Optional[str]
    last_evaluation_at: Optional[datetime]
    certificates_issued: int
