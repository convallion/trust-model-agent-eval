"""Parallel task execution engine."""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Dict, List, Optional, TypeVar

import structlog

logger = structlog.get_logger()

T = TypeVar("T")


@dataclass
class TaskResult:
    """Result of a single task execution."""

    task_id: str
    success: bool
    result: Any
    error: Optional[str] = None
    duration_ms: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class TaskExecutor:
    """
    Parallel task execution with concurrency control.

    Executes evaluation tasks in parallel with configurable
    concurrency limits and timeout handling.
    """

    def __init__(
        self,
        max_concurrency: int = 5,
        timeout_seconds: int = 60,
    ) -> None:
        """
        Initialize the task executor.

        Args:
            max_concurrency: Maximum concurrent tasks
            timeout_seconds: Timeout for individual tasks
        """
        self.max_concurrency = max_concurrency
        self.timeout_seconds = timeout_seconds
        self.semaphore = asyncio.Semaphore(max_concurrency)

    async def execute_task(
        self,
        task_id: str,
        task_fn: Callable[[], Coroutine[Any, Any, T]],
    ) -> TaskResult:
        """
        Execute a single task with timeout and error handling.

        Args:
            task_id: Unique identifier for the task
            task_fn: Async function to execute

        Returns:
            TaskResult with execution details
        """
        started_at = datetime.now(timezone.utc)

        async with self.semaphore:
            try:
                result = await asyncio.wait_for(
                    task_fn(),
                    timeout=self.timeout_seconds,
                )
                completed_at = datetime.now(timezone.utc)

                return TaskResult(
                    task_id=task_id,
                    success=True,
                    result=result,
                    started_at=started_at,
                    completed_at=completed_at,
                    duration_ms=int(
                        (completed_at - started_at).total_seconds() * 1000
                    ),
                )
            except asyncio.TimeoutError:
                logger.warning(f"Task {task_id} timed out")
                return TaskResult(
                    task_id=task_id,
                    success=False,
                    result=None,
                    error=f"Task timed out after {self.timeout_seconds}s",
                    started_at=started_at,
                    completed_at=datetime.now(timezone.utc),
                )
            except Exception as e:
                logger.error(f"Task {task_id} failed", error=str(e))
                return TaskResult(
                    task_id=task_id,
                    success=False,
                    result=None,
                    error=str(e),
                    started_at=started_at,
                    completed_at=datetime.now(timezone.utc),
                )

    async def execute_batch(
        self,
        tasks: List[tuple[str, Callable[[], Coroutine[Any, Any, T]]]],
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> List[TaskResult]:
        """
        Execute multiple tasks in parallel.

        Args:
            tasks: List of (task_id, task_fn) tuples
            progress_callback: Optional callback(completed, total)

        Returns:
            List of TaskResults
        """
        total = len(tasks)
        completed = 0
        results: List[TaskResult] = []

        async def execute_with_progress(
            task_id: str,
            task_fn: Callable[[], Coroutine[Any, Any, T]],
        ) -> TaskResult:
            nonlocal completed
            result = await self.execute_task(task_id, task_fn)
            completed += 1
            if progress_callback:
                progress_callback(completed, total)
            return result

        # Create all task coroutines
        coros = [
            execute_with_progress(task_id, task_fn)
            for task_id, task_fn in tasks
        ]

        # Execute with gather
        results = await asyncio.gather(*coros, return_exceptions=False)

        return results

    async def execute_trials(
        self,
        task_id: str,
        task_fn: Callable[[], Coroutine[Any, Any, T]],
        num_trials: int,
    ) -> List[TaskResult]:
        """
        Execute multiple trials of the same task.

        Used for consistency testing (pass^k evaluation).

        Args:
            task_id: Base identifier for the task
            task_fn: Async function to execute
            num_trials: Number of times to run the task

        Returns:
            List of TaskResults for each trial
        """
        tasks = [
            (f"{task_id}_trial_{i}", task_fn)
            for i in range(num_trials)
        ]
        return await self.execute_batch(tasks)
