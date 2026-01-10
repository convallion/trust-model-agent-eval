"""
TrustModel Certificate Verification Example

This example demonstrates how to verify agent certificates
and use them for trust decisions.
"""

import asyncio
import os

os.environ["TRUSTMODEL_API_KEY"] = "your-api-key-here"

from trustmodel import certificates
from trustmodel.certify import verify, issue, get_certificate


async def verify_certificate():
    """Verify an agent's certificate."""
    certificate_id = "your-certificate-id"

    try:
        verification = await verify(certificate_id)

        print(f"=== Certificate Verification ===")
        print(f"Certificate ID: {verification.certificate_id}")
        print(f"Agent: {verification.agent_name}")
        print(f"Grade: {verification.grade}")
        print(f"\nVerification Status:")
        print(f"  Valid: {'✓' if verification.valid else '✗'}")
        print(f"  Signature Valid: {'✓' if verification.signature_valid else '✗'}")
        print(f"  Not Expired: {'✓' if verification.not_expired else '✗'}")
        print(f"  Not Revoked: {'✓' if verification.not_revoked else '✗'}")

        if verification.capabilities:
            print(f"\nCertified Capabilities:")
            for cap in verification.capabilities:
                print(f"  ✓ {cap}")

        if verification.warnings:
            print(f"\nWarnings:")
            for warning in verification.warnings:
                print(f"  ⚠ {warning}")

    except Exception as e:
        print(f"Verification failed: {e}")


async def issue_new_certificate():
    """Issue a new certificate after evaluation."""
    agent_id = "your-agent-id"
    evaluation_id = "your-evaluation-id"

    cert = await issue(
        agent=agent_id,
        evaluation_id=evaluation_id,
        validity_days=365,  # 1 year validity
    )

    print(f"=== Certificate Issued ===")
    print(f"ID: {cert.id}")
    print(f"Agent: {cert.agent_name}")
    print(f"Grade: {cert.grade}")
    print(f"Overall Score: {cert.scores.overall:.1f}%")
    print(f"Issued: {cert.issued_at}")
    print(f"Expires: {cert.expires_at}")
    print(f"Days until expiry: {cert.days_until_expiry}")

    print(f"\nCapabilities:")
    for cap in cert.capabilities:
        print(f"  ✓ {cap}")


async def check_capability():
    """Check if an agent is certified for a specific capability."""
    certificate_id = "your-certificate-id"

    cert = await get_certificate(certificate_id)

    # Check specific capabilities
    capabilities_to_check = [
        "code_generation",
        "security_analysis",
        "data_processing",
    ]

    print(f"=== Capability Check for {cert.agent_name} ===")
    for cap in capabilities_to_check:
        has_cap = cert.has_capability(cap)
        status = "✓ Certified" if has_cap else "✗ Not Certified"
        print(f"  {cap}: {status}")


async def trust_decision_example():
    """Make a trust decision based on certificate."""

    async def should_trust_agent(agent_certificate_id: str, required_capabilities: list[str]) -> bool:
        """Determine if we should trust an agent for a specific task."""
        try:
            # Verify the certificate
            verification = await verify(agent_certificate_id)

            # Check basic validity
            if not verification.is_fully_valid:
                print(f"Certificate not valid: {verification.errors}")
                return False

            # Check grade requirement
            if verification.grade not in ["A", "B"]:
                print(f"Grade {verification.grade} does not meet minimum requirement (B)")
                return False

            # Check required capabilities
            missing = [
                cap for cap in required_capabilities
                if cap not in verification.capabilities
            ]
            if missing:
                print(f"Missing required capabilities: {missing}")
                return False

            return True

        except Exception as e:
            print(f"Trust verification failed: {e}")
            return False

    # Example usage
    agent_cert_id = "agent-certificate-id"
    required_caps = ["code_review", "security_analysis"]

    trusted = await should_trust_agent(agent_cert_id, required_caps)
    if trusted:
        print("✓ Agent is trusted for this task")
    else:
        print("✗ Agent is not trusted for this task")


if __name__ == "__main__":
    print("=== Verify Certificate ===")
    asyncio.run(verify_certificate())

    print("\n=== Check Capability ===")
    asyncio.run(check_capability())

    print("\n=== Trust Decision ===")
    asyncio.run(trust_decision_example())
