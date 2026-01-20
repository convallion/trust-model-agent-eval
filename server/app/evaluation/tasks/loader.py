"""Task bank loader for evaluation tasks."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterator, Optional

import structlog
import yaml

logger = structlog.get_logger()

# Default path to task definitions
TASKS_DIR = Path(__file__).parent


class GraderType(str, Enum):
    """Types of graders for task evaluation."""

    DETERMINISTIC = "deterministic"
    LLM_JUDGE = "llm_judge"
    COMPOSITE = "composite"


class ExpectedOutcomeType(str, Enum):
    """Types of expected outcomes."""

    FILE_CREATED = "file_created"
    CONTENT_MATCH = "content_match"
    PATTERN_MATCH = "pattern_match"
    LLM_JUDGE = "llm_judge"
    SAFE_REFUSAL = "safe_refusal"
    EXECUTION_SUCCESS = "execution_success"


@dataclass
class ExpectedOutcome:
    """Expected outcome for a task."""

    type: ExpectedOutcomeType
    criteria: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExpectedOutcome":
        """Create from dictionary."""
        return cls(
            type=ExpectedOutcomeType(data.get("type", "llm_judge")),
            criteria=data.get("criteria", {}),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "type": self.type.value,
            "criteria": self.criteria,
        }


@dataclass
class TaskDefinition:
    """Definition of a single evaluation task."""

    id: str
    name: str
    prompt: str
    expected_outcome: ExpectedOutcome
    timeout_seconds: int = 60
    grader_type: GraderType = GraderType.LLM_JUDGE
    category: str = ""
    difficulty: str = "medium"  # easy, medium, hard
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskDefinition":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            prompt=data["prompt"],
            expected_outcome=ExpectedOutcome.from_dict(
                data.get("expected_outcome", {"type": "llm_judge"})
            ),
            timeout_seconds=data.get("timeout_seconds", 60),
            grader_type=GraderType(data.get("grader_type", "llm_judge")),
            category=data.get("category", ""),
            difficulty=data.get("difficulty", "medium"),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "prompt": self.prompt,
            "expected_outcome": self.expected_outcome.to_dict(),
            "timeout_seconds": self.timeout_seconds,
            "grader_type": self.grader_type.value,
            "category": self.category,
            "difficulty": self.difficulty,
            "tags": self.tags,
            "metadata": self.metadata,
        }


class TaskBank:
    """
    Bank of evaluation tasks.

    Loads tasks from YAML files and provides methods to
    query and iterate over tasks.
    """

    def __init__(self, tasks_dir: Optional[Path] = None) -> None:
        """
        Initialize the task bank.

        Args:
            tasks_dir: Directory containing task YAML files
        """
        self.tasks_dir = tasks_dir or TASKS_DIR
        self._tasks: dict[str, TaskDefinition] = {}
        self._tasks_by_category: dict[str, list[TaskDefinition]] = {}
        self._tasks_by_tag: dict[str, list[TaskDefinition]] = {}
        self._loaded = False

    def load(self) -> None:
        """Load all tasks from YAML files."""
        if self._loaded:
            return

        logger.info("Loading task bank", tasks_dir=str(self.tasks_dir))

        # Load all YAML files recursively
        yaml_files = list(self.tasks_dir.rglob("*.yaml")) + list(
            self.tasks_dir.rglob("*.yml")
        )

        for yaml_file in yaml_files:
            try:
                self._load_file(yaml_file)
            except Exception as e:
                logger.error(
                    "Failed to load task file",
                    file=str(yaml_file),
                    error=str(e),
                )

        self._loaded = True
        logger.info(
            "Task bank loaded",
            total_tasks=len(self._tasks),
            categories=list(self._tasks_by_category.keys()),
        )

    def _load_file(self, file_path: Path) -> None:
        """Load tasks from a single YAML file."""
        with open(file_path) as f:
            data = yaml.safe_load(f)

        if not data or "tasks" not in data:
            return

        # Determine category from file path
        relative_path = file_path.relative_to(self.tasks_dir)
        category = relative_path.parent.name if relative_path.parent.name else "general"

        for task_data in data["tasks"]:
            task = TaskDefinition.from_dict(task_data)

            # Set category if not specified
            if not task.category:
                task.category = category

            # Index task
            self._tasks[task.id] = task

            # Index by category
            if task.category not in self._tasks_by_category:
                self._tasks_by_category[task.category] = []
            self._tasks_by_category[task.category].append(task)

            # Index by tags
            for tag in task.tags:
                if tag not in self._tasks_by_tag:
                    self._tasks_by_tag[tag] = []
                self._tasks_by_tag[tag].append(task)

    def get(self, task_id: str) -> Optional[TaskDefinition]:
        """Get a task by ID."""
        self.load()
        return self._tasks.get(task_id)

    def get_by_category(self, category: str) -> list[TaskDefinition]:
        """Get all tasks in a category."""
        self.load()
        return self._tasks_by_category.get(category, [])

    def get_by_tag(self, tag: str) -> list[TaskDefinition]:
        """Get all tasks with a tag."""
        self.load()
        return self._tasks_by_tag.get(tag, [])

    def get_by_difficulty(self, difficulty: str) -> list[TaskDefinition]:
        """Get all tasks with a specific difficulty."""
        self.load()
        return [t for t in self._tasks.values() if t.difficulty == difficulty]

    def get_by_grader_type(self, grader_type: GraderType) -> list[TaskDefinition]:
        """Get all tasks using a specific grader type."""
        self.load()
        return [t for t in self._tasks.values() if t.grader_type == grader_type]

    def sample(
        self,
        n: int,
        category: Optional[str] = None,
        difficulty: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> list[TaskDefinition]:
        """
        Sample n tasks with optional filters.

        Args:
            n: Number of tasks to sample
            category: Filter by category
            difficulty: Filter by difficulty
            tags: Filter by tags (any match)

        Returns:
            List of sampled tasks
        """
        import random

        self.load()

        # Start with all tasks
        pool = list(self._tasks.values())

        # Apply filters
        if category:
            pool = [t for t in pool if t.category == category]
        if difficulty:
            pool = [t for t in pool if t.difficulty == difficulty]
        if tags:
            pool = [t for t in pool if any(tag in t.tags for tag in tags)]

        # Sample
        return random.sample(pool, min(n, len(pool)))

    def all_tasks(self) -> list[TaskDefinition]:
        """Get all tasks."""
        self.load()
        return list(self._tasks.values())

    def categories(self) -> list[str]:
        """Get all available categories."""
        self.load()
        return list(self._tasks_by_category.keys())

    def tags(self) -> list[str]:
        """Get all available tags."""
        self.load()
        return list(self._tasks_by_tag.keys())

    def __len__(self) -> int:
        """Return number of tasks."""
        self.load()
        return len(self._tasks)

    def __iter__(self) -> Iterator[TaskDefinition]:
        """Iterate over all tasks."""
        self.load()
        return iter(self._tasks.values())

    def __contains__(self, task_id: str) -> bool:
        """Check if task exists."""
        self.load()
        return task_id in self._tasks


# Global task bank instances
_capability_tasks: Optional[TaskBank] = None
_safety_tasks: Optional[TaskBank] = None
_reliability_tasks: Optional[TaskBank] = None
_communication_tasks: Optional[TaskBank] = None


def get_capability_tasks() -> TaskBank:
    """Get the capability task bank."""
    global _capability_tasks
    if _capability_tasks is None:
        _capability_tasks = TaskBank(TASKS_DIR / "capability")
    return _capability_tasks


def get_safety_tasks() -> TaskBank:
    """Get the safety task bank."""
    global _safety_tasks
    if _safety_tasks is None:
        _safety_tasks = TaskBank(TASKS_DIR / "safety")
    return _safety_tasks


def get_reliability_tasks() -> TaskBank:
    """Get the reliability task bank."""
    global _reliability_tasks
    if _reliability_tasks is None:
        _reliability_tasks = TaskBank(TASKS_DIR / "reliability")
    return _reliability_tasks


def get_communication_tasks() -> TaskBank:
    """Get the communication task bank."""
    global _communication_tasks
    if _communication_tasks is None:
        _communication_tasks = TaskBank(TASKS_DIR / "communication")
    return _communication_tasks


def get_all_tasks() -> TaskBank:
    """Get a task bank with all tasks."""
    return TaskBank(TASKS_DIR)
