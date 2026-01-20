#!/usr/bin/env python3
"""
Test script for evaluating a LangSmith/LangGraph agent.

Usage:
    1. Start the server: cd server && uvicorn app.main:app --reload
    2. Run this script: python test_langsmith_eval.py
"""

import asyncio
import httpx
import os
from uuid import UUID

# Configuration
API_BASE_URL = "http://localhost:8000"
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY", "")
LANGSMITH_API_URL = os.getenv(
    "LANGSMITH_API_URL",
    "https://prod-deepagents-agent-build-d4c1479ed8ce53fbb8c3eefc91f0aa7d.us.langgraph.app"
)

# Test user credentials (for initial setup)
TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "testpassword123"
TEST_ORG = "TestOrganization"


async def main():
    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=60.0) as client:
        print("=" * 60)
        print("TrustModel Agent Eval - LangSmith Agent Test")
        print("=" * 60)

        # Step 1: Register or login
        print("\n[1] Authenticating...")
        token = await authenticate(client)
        if not token:
            print("❌ Authentication failed")
            return
        print(f"✓ Authenticated successfully")

        # Set auth header
        client.headers["Authorization"] = f"Bearer {token}"

        # Step 2: Register the LangSmith agent
        print("\n[2] Registering LangSmith agent...")
        agent_id = await register_agent(client)
        if not agent_id:
            print("❌ Agent registration failed")
            return
        print(f"✓ Agent registered: {agent_id}")

        # Step 3: Start evaluation
        print("\n[3] Starting evaluation...")
        evaluation_id = await start_evaluation(client, agent_id)
        if not evaluation_id:
            print("❌ Failed to start evaluation")
            return
        print(f"✓ Evaluation started: {evaluation_id}")

        # Step 4: Poll for results
        print("\n[4] Waiting for evaluation to complete...")
        results = await wait_for_evaluation(client, evaluation_id)

        if results:
            print("\n" + "=" * 60)
            print("EVALUATION RESULTS")
            print("=" * 60)
            print(f"Status: {results.get('status')}")
            print(f"Overall Score: {results.get('overall_score')}")
            print(f"Grade: {results.get('grade')}")
            print(f"Certificate Eligible: {results.get('certificate_eligible')}")
            print("\nSuite Scores:")
            print(f"  - Capability: {results.get('capability_score')}")
            print(f"  - Safety: {results.get('safety_score')}")
            print(f"  - Reliability: {results.get('reliability_score')}")
            print(f"  - Communication: {results.get('communication_score')}")

            if results.get('error_message'):
                print(f"\nError: {results.get('error_message')}")
        else:
            print("❌ Failed to get evaluation results")


async def authenticate(client: httpx.AsyncClient) -> str | None:
    """Register or login and return access token."""

    # Try to register first
    register_response = await client.post(
        "/v1/auth/register",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "full_name": "Test User",
            "organization_name": TEST_ORG,
        }
    )

    if register_response.status_code == 201:
        data = register_response.json()
        return data.get("access_token")

    # If registration fails (user exists), try login
    login_response = await client.post(
        "/v1/auth/login",
        data={
            "username": TEST_EMAIL,
            "password": TEST_PASSWORD,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )

    if login_response.status_code == 200:
        data = login_response.json()
        return data.get("access_token")

    print(f"Auth error: {login_response.text}")
    return None


async def register_agent(client: httpx.AsyncClient) -> str | None:
    """Register the LangSmith agent."""

    # Check if agent already exists
    list_response = await client.get("/v1/agents")
    if list_response.status_code == 200:
        agents = list_response.json().get("items", [])
        for agent in agents:
            if agent.get("name") == "LangSmith Test Agent":
                return agent.get("id")

    # Register new agent
    response = await client.post(
        "/v1/agents",
        json={
            "name": "LangSmith Test Agent",
            "description": "LangGraph agent for evaluation testing",
            "agent_type": "custom",
            "framework": "LangGraph",
            "version": "1.0.0",
            "declared_capabilities": [
                "code_generation",
                "code_review",
                "debugging",
                "documentation",
                "testing",
            ],
            "metadata": {
                "executor_type": "langsmith",
                "langsmith_api_key": LANGSMITH_API_KEY,
                "langsmith_api_url": LANGSMITH_API_URL,
                # If your agent has a specific assistant ID, add it here:
                # "langsmith_agent_id": "your-assistant-id",
            }
        }
    )

    if response.status_code == 201:
        return response.json().get("id")

    print(f"Agent registration error: {response.text}")
    return None


async def start_evaluation(client: httpx.AsyncClient, agent_id: str) -> str | None:
    """Start an evaluation run."""

    response = await client.post(
        "/v1/evaluations",
        json={
            "agent_id": agent_id,
            "suites": ["capability", "safety", "reliability"],
            "config": {
                "trials_per_task": 1,  # Set to 1 for quick testing
                "parallel": 3,
                "timeout_minutes": 30,
            }
        }
    )

    if response.status_code == 201:
        return response.json().get("id")

    print(f"Evaluation start error: {response.text}")
    return None


async def wait_for_evaluation(
    client: httpx.AsyncClient,
    evaluation_id: str,
    max_wait_seconds: int = 1800,  # 30 minutes
) -> dict | None:
    """Poll for evaluation completion."""

    poll_interval = 5  # seconds
    elapsed = 0

    while elapsed < max_wait_seconds:
        response = await client.get(f"/v1/evaluations/{evaluation_id}")

        if response.status_code != 200:
            print(f"Error polling: {response.text}")
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
            continue

        data = response.json()
        status = data.get("status")
        progress = data.get("progress_percent", 0)
        current_suite = data.get("current_suite", "")
        current_test = data.get("current_test", "")

        # Print progress
        print(f"\r  Progress: {progress}% - {current_suite}/{current_test}    ", end="", flush=True)

        if status == "completed":
            print()  # New line after progress
            return data

        if status in ("failed", "cancelled"):
            print()
            print(f"Evaluation {status}: {data.get('error_message')}")
            return data

        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

    print("\nTimeout waiting for evaluation")
    return None


if __name__ == "__main__":
    asyncio.run(main())
