"""
TrustModel Evaluation Example

This example demonstrates how to run evaluations on agents
and interpret the results.
"""

import asyncio
import os

os.environ["TRUSTMODEL_API_KEY"] = "your-api-key-here"

from trustmodel import evaluate
from trustmodel.models.evaluation import EvaluationSuite


async def run_full_evaluation():
    """Run a full evaluation on an agent."""
    print("Starting full evaluation...")

    results = await evaluate(
        agent="my-agent",  # Agent name or ID
        suites=["capability", "safety", "reliability", "communication"],
        wait=True,  # Wait for completion
        timeout=600,  # 10 minute timeout
    )

    print(f"\n=== Evaluation Results ===")
    print(f"Status: {results.status.value}")
    print(f"Grade: {results.grade}")

    print(f"\n=== Scores ===")
    print(f"Overall: {results.scores.overall:.1f}%")
    if results.scores.capability:
        print(f"Capability: {results.scores.capability:.1f}%")
    if results.scores.safety:
        print(f"Safety: {results.scores.safety:.1f}%")
    if results.scores.reliability:
        print(f"Reliability: {results.scores.reliability:.1f}%")
    if results.scores.communication:
        print(f"Communication: {results.scores.communication:.1f}%")

    print(f"\n=== Certified Capabilities ===")
    for cap in results.certified_capabilities:
        print(f"  ✓ {cap}")

    if results.not_certified:
        print(f"\n=== Not Certified ===")
        for cap in results.not_certified:
            print(f"  ✗ {cap}")

    # Detailed suite results
    for suite_result in results.suite_results:
        print(f"\n=== {suite_result.suite.value.title()} Suite ===")
        print(f"Score: {suite_result.score:.1f}%")
        print(f"Passed: {suite_result.passed}/{suite_result.total}")

        # Show failed tasks
        failed_tasks = [t for t in suite_result.tasks if not t.passed]
        if failed_tasks:
            print("Failed tasks:")
            for task in failed_tasks[:5]:
                print(f"  - {task.task_name}: {task.feedback}")

    return results


async def run_safety_only():
    """Run only safety evaluation."""
    print("Running safety evaluation only...")

    results = await evaluate(
        agent="my-agent",
        suites=["safety"],
    )

    print(f"Safety Score: {results.scores.safety:.1f}%")

    # Check specific safety categories
    safety_result = results.get_suite_result(EvaluationSuite.safety)
    if safety_result:
        print("\nSafety Categories:")
        for category, score in safety_result.categories.items():
            status = "✓" if score >= 85 else "✗"
            print(f"  {status} {category}: {score:.1f}%")


async def evaluate_with_traces():
    """Run evaluation using specific traces as context."""
    print("Running evaluation with trace context...")

    # Get recent trace IDs (you would get these from your trace collection)
    trace_ids = [
        "trace-uuid-1",
        "trace-uuid-2",
    ]

    results = await evaluate(
        agent="my-agent",
        suites=["capability"],
        trace_ids=trace_ids,  # Use these traces for context
    )

    print(f"Capability Score: {results.scores.capability:.1f}%")


if __name__ == "__main__":
    print("=== Full Evaluation ===")
    asyncio.run(run_full_evaluation())

    print("\n=== Safety Only ===")
    asyncio.run(run_safety_only())
