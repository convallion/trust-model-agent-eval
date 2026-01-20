"""Graders module for LLM-as-Judge evaluation."""

from typing import Optional, Type

from app.evaluation.graders.base import (
    BaseGrader,
    CompositeGrader,
    DeterministicGrader,
    GradeLevel,
    GradeResult,
    GradingContext,
    LLMGrader,
)
from app.evaluation.graders.openrouter_client import (
    OpenRouterClient,
    OpenRouterError,
    OpenRouterRateLimitError,
    close_openrouter_client,
    get_openrouter_client,
)
from app.evaluation.graders.reasoning_grader import (
    EfficiencyGrader,
    ReasoningQualityGrader,
    TaskCompletionGrader,
    ToolProficiencyGrader,
)
from app.evaluation.graders.safety_grader import (
    BoundaryAdherenceGrader,
    DataProtectionGrader,
    HarmfulActionGrader,
    JailbreakDetectionGrader,
    QuickSafetyGrader,
)

__all__ = [
    # Base classes
    "BaseGrader",
    "DeterministicGrader",
    "LLMGrader",
    "CompositeGrader",
    "GradeResult",
    "GradeLevel",
    "GradingContext",
    # OpenRouter client
    "OpenRouterClient",
    "OpenRouterError",
    "OpenRouterRateLimitError",
    "get_openrouter_client",
    "close_openrouter_client",
    # Capability graders
    "ReasoningQualityGrader",
    "TaskCompletionGrader",
    "ToolProficiencyGrader",
    "EfficiencyGrader",
    # Safety graders
    "JailbreakDetectionGrader",
    "BoundaryAdherenceGrader",
    "DataProtectionGrader",
    "HarmfulActionGrader",
    "QuickSafetyGrader",
    # Factory
    "get_grader",
    "GraderType",
]


class GraderType:
    """Available grader types."""

    # Capability graders
    TASK_COMPLETION = "task_completion"
    TOOL_PROFICIENCY = "tool_proficiency"
    REASONING_QUALITY = "reasoning_quality"
    EFFICIENCY = "efficiency"

    # Safety graders
    JAILBREAK_DETECTION = "jailbreak_detection"
    BOUNDARY_ADHERENCE = "boundary_adherence"
    DATA_PROTECTION = "data_protection"
    HARMFUL_ACTION_BLOCKING = "harmful_action_blocking"
    QUICK_SAFETY = "quick_safety"

    # Meta graders
    DETERMINISTIC = "deterministic"
    COMPOSITE = "composite"


# Registry of grader classes
_GRADER_REGISTRY: dict[str, Type[BaseGrader]] = {
    GraderType.TASK_COMPLETION: TaskCompletionGrader,
    GraderType.TOOL_PROFICIENCY: ToolProficiencyGrader,
    GraderType.REASONING_QUALITY: ReasoningQualityGrader,
    GraderType.EFFICIENCY: EfficiencyGrader,
    GraderType.JAILBREAK_DETECTION: JailbreakDetectionGrader,
    GraderType.BOUNDARY_ADHERENCE: BoundaryAdherenceGrader,
    GraderType.DATA_PROTECTION: DataProtectionGrader,
    GraderType.HARMFUL_ACTION_BLOCKING: HarmfulActionGrader,
    GraderType.QUICK_SAFETY: QuickSafetyGrader,
}


def get_grader(
    grader_type: str,
    client: Optional[OpenRouterClient] = None,
    **kwargs,
) -> BaseGrader:
    """
    Factory function to get a grader by type.

    Args:
        grader_type: The type of grader to create
        client: Optional OpenRouter client to use
        **kwargs: Additional arguments for the grader

    Returns:
        An instance of the requested grader

    Raises:
        ValueError: If the grader type is not recognized
    """
    if grader_type not in _GRADER_REGISTRY:
        raise ValueError(
            f"Unknown grader type: {grader_type}. "
            f"Available types: {list(_GRADER_REGISTRY.keys())}"
        )

    grader_class = _GRADER_REGISTRY[grader_type]

    # Handle special cases
    if grader_type == GraderType.QUICK_SAFETY:
        return grader_class()

    if grader_type == GraderType.DETERMINISTIC:
        return DeterministicGrader(criteria=kwargs.get("criteria", {}))

    # LLM graders need client
    if issubclass(grader_class, LLMGrader):
        return grader_class(client=client, **kwargs)

    return grader_class(**kwargs)


def create_capability_graders(
    client: Optional[OpenRouterClient] = None,
) -> dict[str, BaseGrader]:
    """Create all capability graders."""
    return {
        "task_completion": get_grader(GraderType.TASK_COMPLETION, client),
        "tool_proficiency": get_grader(GraderType.TOOL_PROFICIENCY, client),
        "reasoning_quality": get_grader(GraderType.REASONING_QUALITY, client),
        "efficiency": get_grader(GraderType.EFFICIENCY, client),
    }


def create_safety_graders(
    client: Optional[OpenRouterClient] = None,
) -> dict[str, BaseGrader]:
    """Create all safety graders."""
    return {
        "jailbreak_detection": get_grader(GraderType.JAILBREAK_DETECTION, client),
        "boundary_adherence": get_grader(GraderType.BOUNDARY_ADHERENCE, client),
        "data_protection": get_grader(GraderType.DATA_PROTECTION, client),
        "harmful_action_blocking": get_grader(GraderType.HARMFUL_ACTION_BLOCKING, client),
        "quick_safety": get_grader(GraderType.QUICK_SAFETY),
    }
