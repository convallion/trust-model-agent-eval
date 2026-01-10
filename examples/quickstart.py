"""
TrustModel Quickstart Example

This example demonstrates the basic usage of the TrustModel SDK:
1. Instrumenting an agent
2. Running an evaluation
3. Issuing a certificate
"""

import asyncio
from trustmodel import instrument, evaluate, certificates


async def main():
    # 1. Instrument your agent
    # This registers the agent and enables automatic tracing
    handle = instrument(
        agent_name="quickstart-agent",
        api_key="your-api-key-here",  # Set TRUSTMODEL_API_KEY env var instead
    )

    print(f"Agent registered: {handle.agent_name} (ID: {handle.agent_id})")

    # 2. Your agent does some work...
    # All LLM calls are automatically traced
    # (Simulated here - in real use, your agent would make LLM calls)

    # 3. Run an evaluation
    print("\nRunning evaluation...")
    results = await evaluate(
        agent=handle.agent_id,
        suites=["capability", "safety", "reliability", "communication"],
    )

    print(f"Evaluation complete!")
    print(f"  Grade: {results.grade}")
    print(f"  Overall Score: {results.scores.overall:.1f}")
    print(f"  Safety Score: {results.scores.safety:.1f}")

    # 4. Issue a certificate if eligible
    if results.is_certifiable:
        print("\nAgent is eligible for certification!")
        cert = await certificates.issue(
            agent=handle.agent_id,
            evaluation_id=results.id,
        )
        print(f"Certificate issued: {cert.id}")
        print(f"  Grade: {cert.grade}")
        print(f"  Valid until: {cert.expires_at}")
        print(f"  Capabilities: {', '.join(cert.capabilities)}")
    else:
        print("\nAgent does not meet certification requirements.")
        print(f"  Minimum overall score: 70 (got {results.scores.overall:.1f})")
        print(f"  Minimum safety score: 85 (got {results.scores.safety:.1f})")

    # 5. Cleanup
    handle.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
