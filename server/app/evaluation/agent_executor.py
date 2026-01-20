"""Agent executor for running evaluation tasks against agents."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

import httpx
import structlog

from app.config import settings
from app.evaluation.tasks import TaskDefinition

logger = structlog.get_logger()


@dataclass
class ExecutionResult:
    """Result of executing a task against an agent."""

    task_id: str
    agent_id: UUID
    execution_id: UUID = field(default_factory=uuid4)

    # Response
    response: str = ""
    success: bool = False
    error: Optional[str] = None

    # Timing
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    duration_ms: int = 0

    # Trace data (if available)
    trace_data: dict[str, Any] = field(default_factory=dict)

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    def complete(self, response: str, success: bool = True) -> None:
        """Mark execution as complete."""
        self.response = response
        self.success = success
        self.completed_at = datetime.now(timezone.utc)
        self.duration_ms = int(
            (self.completed_at - self.started_at).total_seconds() * 1000
        )

    def fail(self, error: str) -> None:
        """Mark execution as failed."""
        self.error = error
        self.success = False
        self.completed_at = datetime.now(timezone.utc)
        self.duration_ms = int(
            (self.completed_at - self.started_at).total_seconds() * 1000
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "agent_id": str(self.agent_id),
            "execution_id": str(self.execution_id),
            "response": self.response,
            "success": self.success,
            "error": self.error,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
            "trace_data": self.trace_data,
            "metadata": self.metadata,
        }


class BaseAgentExecutor(ABC):
    """Base class for agent executors."""

    def __init__(
        self,
        agent_id: UUID,
        timeout_seconds: int = 60,
    ) -> None:
        """
        Initialize the executor.

        Args:
            agent_id: ID of the agent to execute against
            timeout_seconds: Default timeout for executions
        """
        self.agent_id = agent_id
        self.timeout_seconds = timeout_seconds

    @abstractmethod
    async def execute(
        self,
        task: TaskDefinition,
        timeout_seconds: Optional[int] = None,
    ) -> ExecutionResult:
        """
        Execute a task against the agent.

        Args:
            task: Task definition to execute
            timeout_seconds: Override timeout

        Returns:
            ExecutionResult with response and metadata
        """
        pass

    async def execute_batch(
        self,
        tasks: list[TaskDefinition],
        max_concurrency: int = 5,
    ) -> list[ExecutionResult]:
        """
        Execute multiple tasks concurrently.

        Args:
            tasks: List of tasks to execute
            max_concurrency: Maximum concurrent executions

        Returns:
            List of ExecutionResults
        """
        semaphore = asyncio.Semaphore(max_concurrency)

        async def execute_with_semaphore(task: TaskDefinition) -> ExecutionResult:
            async with semaphore:
                return await self.execute(task)

        results = await asyncio.gather(
            *[execute_with_semaphore(task) for task in tasks],
            return_exceptions=True,
        )

        # Handle any exceptions
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append(
                    ExecutionResult(
                        task_id=tasks[i].id,
                        agent_id=self.agent_id,
                        success=False,
                        error=str(result),
                    )
                )
            else:
                final_results.append(result)

        return final_results


class LangSmithAgentExecutor(BaseAgentExecutor):
    """
    Executor for LangSmith/LangGraph agents.

    Connects to LangGraph deployed agents and executes tasks.
    """

    def __init__(
        self,
        agent_id: UUID,
        langsmith_api_key: Optional[str] = None,
        langsmith_api_url: Optional[str] = None,
        langsmith_agent_id: Optional[str] = None,
        timeout_seconds: int = 120,
    ) -> None:
        """
        Initialize the LangSmith executor.

        Args:
            agent_id: Internal agent ID
            langsmith_api_key: LangSmith API key
            langsmith_api_url: LangGraph agent API URL
            langsmith_agent_id: LangSmith/LangGraph agent UUID
            timeout_seconds: Execution timeout
        """
        super().__init__(agent_id, timeout_seconds)

        self.api_key = langsmith_api_key or settings.langsmith_api_key
        self.api_url = langsmith_api_url or settings.langsmith_api_url
        self.langsmith_agent_id = langsmith_agent_id

        if not self.api_key:
            raise ValueError("LangSmith API key is required")
        if not self.api_url:
            raise ValueError("LangSmith API URL is required")

        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.api_url,
                headers={
                    "X-Auth-Scheme": "langsmith-api-key",
                    "x-api-key": self.api_key,
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(self.timeout_seconds),
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def execute(
        self,
        task: TaskDefinition,
        timeout_seconds: Optional[int] = None,
    ) -> ExecutionResult:
        """Execute a task against the LangSmith agent."""
        result = ExecutionResult(
            task_id=task.id,
            agent_id=self.agent_id,
        )

        timeout = timeout_seconds or task.timeout_seconds or self.timeout_seconds

        try:
            client = await self._get_client()

            # Create a new thread
            thread_response = await client.post("/threads")
            if thread_response.status_code != 200:
                result.fail(f"Failed to create thread: {thread_response.text}")
                return result

            thread = thread_response.json()
            thread_id = thread["thread_id"]

            result.metadata["thread_id"] = thread_id

            # Run the agent with the task prompt
            run_response = await asyncio.wait_for(
                client.post(
                    f"/threads/{thread_id}/runs",
                    json={
                        "assistant_id": self.langsmith_agent_id,
                        "input": {
                            "messages": [
                                {"type": "human", "content": task.prompt}
                            ]
                        },
                    },
                ),
                timeout=timeout,
            )

            if run_response.status_code != 200:
                result.fail(f"Failed to start run: {run_response.text}")
                return result

            run = run_response.json()
            run_id = run.get("run_id")
            result.metadata["run_id"] = run_id

            # Wait for the run to complete
            response_text = await self._wait_for_completion(
                client, thread_id, run_id, timeout
            )

            result.complete(response_text, success=True)

            # Try to get trace data
            try:
                trace_response = await client.get(f"/runs/{run_id}/trace")
                if trace_response.status_code == 200:
                    result.trace_data = trace_response.json()
            except Exception as e:
                logger.warning(f"Failed to get trace: {e}")

        except asyncio.TimeoutError:
            result.fail(f"Execution timed out after {timeout}s")
        except Exception as e:
            logger.error(f"LangSmith execution failed: {e}")
            result.fail(str(e))

        return result

    async def _wait_for_completion(
        self,
        client: httpx.AsyncClient,
        thread_id: str,
        run_id: str,
        timeout: int,
    ) -> str:
        """Wait for a run to complete and return the response."""
        start_time = datetime.now(timezone.utc)
        poll_interval = 1.0  # seconds

        while True:
            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            if elapsed > timeout:
                raise asyncio.TimeoutError()

            # Check run status
            status_response = await client.get(f"/threads/{thread_id}/runs/{run_id}")
            if status_response.status_code != 200:
                await asyncio.sleep(poll_interval)
                continue

            run_status = status_response.json()
            status = run_status.get("status")

            if status == "completed":
                # Get the messages
                messages_response = await client.get(f"/threads/{thread_id}/messages")
                if messages_response.status_code == 200:
                    messages = messages_response.json()
                    # Return the last assistant message
                    for msg in reversed(messages.get("messages", [])):
                        if msg.get("type") == "ai" or msg.get("role") == "assistant":
                            content = msg.get("content", "")
                            if isinstance(content, list):
                                # Handle structured content
                                return " ".join(
                                    c.get("text", str(c)) for c in content
                                )
                            return content
                return ""

            elif status in ("failed", "cancelled", "error"):
                error = run_status.get("error", "Unknown error")
                raise Exception(f"Run failed: {error}")

            await asyncio.sleep(poll_interval)


class MockAgentExecutor(BaseAgentExecutor):
    """
    Mock executor for testing without a real agent.

    Can be configured with predetermined responses.
    """

    def __init__(
        self,
        agent_id: UUID,
        responses: Optional[dict[str, str]] = None,
        default_response: str = "This is a mock response.",
        success_rate: float = 0.95,
    ) -> None:
        """
        Initialize the mock executor.

        Args:
            agent_id: Agent ID
            responses: Dict mapping task_id to response
            default_response: Default response if task_id not in responses
            success_rate: Probability of success (0-1)
        """
        super().__init__(agent_id)
        self.responses = responses or {}
        self.default_response = default_response
        self.success_rate = success_rate

    async def execute(
        self,
        task: TaskDefinition,
        timeout_seconds: Optional[int] = None,
    ) -> ExecutionResult:
        """Execute a mock task."""
        import random

        result = ExecutionResult(
            task_id=task.id,
            agent_id=self.agent_id,
        )

        # Simulate some execution time
        await asyncio.sleep(random.uniform(0.1, 0.5))

        # Determine success based on success_rate
        if random.random() < self.success_rate:
            response = self.responses.get(task.id, self.default_response)
            result.complete(response, success=True)
        else:
            result.fail("Mock execution failure")

        return result


class HTTPAgentExecutor(BaseAgentExecutor):
    """
    Generic HTTP executor for agents with REST APIs.

    Sends task prompts to an HTTP endpoint and captures responses.
    """

    def __init__(
        self,
        agent_id: UUID,
        endpoint_url: str,
        api_key: Optional[str] = None,
        method: str = "POST",
        request_template: Optional[dict[str, Any]] = None,
        response_path: str = "response",
        timeout_seconds: int = 60,
    ) -> None:
        """
        Initialize the HTTP executor.

        Args:
            agent_id: Agent ID
            endpoint_url: URL to send requests to
            api_key: Optional API key for authentication
            method: HTTP method (POST, GET)
            request_template: Template for request body
            response_path: JSON path to response content
            timeout_seconds: Request timeout
        """
        super().__init__(agent_id, timeout_seconds)
        self.endpoint_url = endpoint_url
        self.api_key = api_key
        self.method = method
        self.request_template = request_template or {"prompt": "{prompt}"}
        self.response_path = response_path
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            self._client = httpx.AsyncClient(
                headers=headers,
                timeout=httpx.Timeout(self.timeout_seconds),
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def execute(
        self,
        task: TaskDefinition,
        timeout_seconds: Optional[int] = None,
    ) -> ExecutionResult:
        """Execute a task via HTTP."""
        result = ExecutionResult(
            task_id=task.id,
            agent_id=self.agent_id,
        )

        timeout = timeout_seconds or task.timeout_seconds or self.timeout_seconds

        try:
            client = await self._get_client()

            # Build request body
            body = self._build_request_body(task)

            # Make request
            response = await asyncio.wait_for(
                client.request(
                    method=self.method,
                    url=self.endpoint_url,
                    json=body,
                ),
                timeout=timeout,
            )

            if response.status_code >= 400:
                result.fail(f"HTTP {response.status_code}: {response.text}")
                return result

            # Extract response
            response_data = response.json()
            response_text = self._extract_response(response_data)

            result.complete(response_text, success=True)

        except asyncio.TimeoutError:
            result.fail(f"Request timed out after {timeout}s")
        except Exception as e:
            logger.error(f"HTTP execution failed: {e}")
            result.fail(str(e))

        return result

    def _build_request_body(self, task: TaskDefinition) -> dict[str, Any]:
        """Build request body from template."""
        import copy
        import json

        body = copy.deepcopy(self.request_template)

        # Replace {prompt} placeholder
        body_str = json.dumps(body)
        body_str = body_str.replace("{prompt}", task.prompt.replace('"', '\\"'))
        body_str = body_str.replace("{task_id}", task.id)

        return json.loads(body_str)

    def _extract_response(self, data: dict[str, Any]) -> str:
        """Extract response text from response data using path."""
        parts = self.response_path.split(".")
        current = data

        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            elif isinstance(current, list) and part.isdigit():
                current = current[int(part)]
            else:
                return str(current)

        return str(current)


# Factory function
def create_executor(
    agent_id: UUID,
    executor_type: str,
    **kwargs: Any,
) -> BaseAgentExecutor:
    """
    Factory function to create an agent executor.

    Args:
        agent_id: Agent ID
        executor_type: Type of executor ("langsmith", "http", "mock")
        **kwargs: Additional arguments for the executor

    Returns:
        Configured executor instance
    """
    executors = {
        "langsmith": LangSmithAgentExecutor,
        "http": HTTPAgentExecutor,
        "mock": MockAgentExecutor,
    }

    if executor_type not in executors:
        raise ValueError(f"Unknown executor type: {executor_type}")

    return executors[executor_type](agent_id=agent_id, **kwargs)
