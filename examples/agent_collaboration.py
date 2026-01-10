"""
TrustModel Agent Collaboration Example

This example demonstrates the TACP (TrustModel Agent Communication Protocol)
for secure agent-to-agent communication with trust verification.
"""

import asyncio
import os

os.environ["TRUSTMODEL_API_KEY"] = "your-api-key-here"
os.environ["TRUSTMODEL_AGENT_ID"] = "your-agent-id"

from trustmodel import connect, instrument
from trustmodel.protocol import TACPSession


async def basic_collaboration():
    """Basic agent-to-agent collaboration."""

    # Connect to another agent
    async with await connect(
        to_agent="research-lab/paper-analyzer",
        purpose="Research security best practices for JWT authentication",
        needed_capabilities=["research", "analysis"],
        verify_trust=True,  # Verify the agent's certificate before proceeding
        minimum_grade="B",  # Require at least a B grade
    ) as session:
        print(f"Connected to {session.remote_agent_name}")
        print(f"Trust verified: {session.is_trusted}")

        # Request a task
        result = await session.request_task(
            task_type="research",
            description="Find best practices for JWT authentication in Python",
            parameters={
                "focus_areas": ["security", "implementation"],
                "max_results": 10,
            },
            timeout=60.0,
        )

        if result.success:
            print(f"Task completed successfully!")
            print(f"Result: {result.result}")
        else:
            print(f"Task failed: {result.error}")


async def query_capabilities():
    """Query another agent's capabilities before connecting."""

    session = await connect(
        to_agent="code-review-agent",
        purpose="Code review collaboration",
        verify_trust=False,  # Don't verify yet
    )

    try:
        # Query capabilities
        capabilities = await session.query_capabilities(
            capabilities=["code_review", "security_analysis", "testing"],
            include_scores=True,
        )

        print(f"Agent: {capabilities.agent_name}")
        print(f"Certificate Grade: {capabilities.certificate_grade}")
        print("\nCapabilities:")
        for cap, has_cap in capabilities.capabilities.items():
            score = capabilities.scores.get(cap, 0) if capabilities.scores else 0
            status = "✓" if has_cap else "✗"
            print(f"  {status} {cap}: {score:.1f}%")

        # Now verify trust if capabilities look good
        if capabilities.capabilities.get("code_review"):
            await session.verify_trust(
                required_capabilities=["code_review"],
                minimum_grade="C",
            )
            print("\nTrust verified!")

    finally:
        await session.end()


async def task_with_progress():
    """Request a task with progress updates."""

    def on_progress(progress):
        """Handle progress updates."""
        print(f"Progress: {progress.progress * 100:.0f}% - {progress.status}")
        if progress.message:
            print(f"  Message: {progress.message}")

    async with await connect(
        to_agent="data-analysis-agent",
        purpose="Analyze dataset",
        needed_capabilities=["data_analysis"],
    ) as session:
        result = await session.request_task(
            task_type="analyze",
            description="Analyze the user behavior dataset",
            parameters={
                "dataset_id": "user-behavior-2024",
                "analysis_type": "trends",
            },
            timeout=300.0,
            on_progress=on_progress,
        )

        print(f"\nFinal result: {result.result}")


async def respond_to_requests():
    """Handle incoming task requests (responder side)."""
    from trustmodel.protocol import TACPClient
    from trustmodel.models.protocol import MessageType

    client = TACPClient()

    # List pending session requests
    pending = await client.list_pending()
    print(f"Pending session requests: {len(pending)}")

    for request in pending:
        print(f"\nSession request from: {request['initiator_agent_name']}")
        print(f"Purpose: {request['purpose']}")

        # Accept the session
        session = await client.accept(request["id"])

        # Handle incoming messages
        @session.on_message(MessageType.task_request)
        async def handle_task(message):
            task = message.payload
            print(f"Received task: {task['description']}")

            # Process the task (your agent logic here)
            result = {"status": "completed", "data": "..."}

            # Send response
            await session.send_message(
                MessageType.task_complete,
                {
                    "task_id": task["task_id"],
                    "success": True,
                    "result": result,
                },
                in_reply_to=message.message_id,
            )

        # Keep session alive for handling requests
        await asyncio.sleep(60)
        await session.end()


if __name__ == "__main__":
    print("=== Basic Collaboration ===")
    asyncio.run(basic_collaboration())

    print("\n=== Query Capabilities ===")
    asyncio.run(query_capabilities())

    print("\n=== Task with Progress ===")
    asyncio.run(task_with_progress())
