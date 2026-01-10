"""Certificate management client."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from trustmodel.api.client import TrustModelClient, get_client
from trustmodel.core.exceptions import CertificateError, CertificateExpiredError, CertificateRevokedError
from trustmodel.core.logging import get_logger
from trustmodel.models.certificate import (
    Certificate,
    CertificateScores,
    CertificateStatus,
    CertificateVerification,
    SafetyAttestation,
)

logger = get_logger(__name__)


class CertificateClient:
    """Client for managing trust certificates."""

    def __init__(self, client: Optional[TrustModelClient] = None) -> None:
        self._client = client or get_client()

    async def issue(
        self,
        agent_id: UUID,
        evaluation_id: UUID,
        validity_days: int = 365,
    ) -> Certificate:
        """
        Issue a trust certificate based on evaluation results.

        Args:
            agent_id: The agent to certify
            evaluation_id: The evaluation to base the certificate on
            validity_days: How long the certificate is valid (default: 365)

        Returns:
            The issued Certificate

        Raises:
            CertificateError: If the evaluation doesn't meet certification requirements
        """
        response = await self._client.issue_certificate({
            "agent_id": str(agent_id),
            "evaluation_id": str(evaluation_id),
            "validity_days": validity_days,
        })

        logger.info(
            "Issued certificate",
            certificate_id=response["id"],
            agent_id=str(agent_id),
            grade=response.get("grade"),
        )

        return self._parse_certificate(response)

    async def get(self, certificate_id: UUID) -> Certificate:
        """Get certificate details."""
        response = await self._client.get_certificate(certificate_id)
        return self._parse_certificate(response)

    async def verify(self, certificate_id: UUID) -> CertificateVerification:
        """
        Verify a certificate's validity.

        This checks:
        - Cryptographic signature validity
        - Expiration status
        - Revocation status

        Args:
            certificate_id: The certificate to verify

        Returns:
            CertificateVerification with detailed status

        Raises:
            CertificateExpiredError: If certificate has expired
            CertificateRevokedError: If certificate has been revoked
        """
        response = await self._client.verify_certificate(certificate_id)

        verification = CertificateVerification(
            certificate_id=UUID(response["certificate_id"]),
            valid=response["valid"],
            status=CertificateStatus(response["status"]),
            signature_valid=response["signature_valid"],
            not_expired=response["not_expired"],
            not_revoked=response["not_revoked"],
            agent_id=UUID(response["agent_id"]),
            agent_name=response["agent_name"],
            grade=response["grade"],
            capabilities=response.get("capabilities", []),
            issued_at=datetime.fromisoformat(response["issued_at"]),
            expires_at=datetime.fromisoformat(response["expires_at"]),
            verified_at=datetime.fromisoformat(response["verified_at"]),
            errors=response.get("errors", []),
            warnings=response.get("warnings", []),
        )

        # Raise specific errors for invalid certificates
        if not verification.not_expired:
            raise CertificateExpiredError(
                certificate_id=str(certificate_id),
                expired_at=verification.expires_at.isoformat(),
            )

        if not verification.not_revoked:
            raise CertificateRevokedError(
                certificate_id=str(certificate_id),
                revoked_at=response.get("revoked_at", "unknown"),
                revocation_reason=response.get("revocation_reason"),
            )

        return verification

    async def revoke(
        self,
        certificate_id: UUID,
        reason: str,
    ) -> Certificate:
        """
        Revoke a certificate.

        Args:
            certificate_id: The certificate to revoke
            reason: Reason for revocation

        Returns:
            The revoked Certificate
        """
        response = await self._client.revoke_certificate(certificate_id, reason)

        logger.info(
            "Revoked certificate",
            certificate_id=str(certificate_id),
            reason=reason,
        )

        return self._parse_certificate(response)

    async def list(
        self,
        agent_id: Optional[UUID] = None,
        status: Optional[CertificateStatus] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Certificate], int]:
        """List certificates with optional filters."""
        # Use the client's list method when implemented
        # For now, use search
        response = await self._client.search_registry(
            agent_name=None,
            min_grade=None,
        )

        certificates = [self._parse_certificate(c) for c in response.get("items", [])]
        total = response.get("total", len(certificates))

        return certificates, total

    async def check_capability(
        self,
        certificate_id: UUID,
        capability: str,
    ) -> bool:
        """
        Check if a certificate attests to a specific capability.

        Args:
            certificate_id: The certificate to check
            capability: The capability to verify

        Returns:
            True if the certificate includes the capability
        """
        certificate = await self.get(certificate_id)
        return certificate.has_capability(capability)

    def _parse_certificate(self, data: dict[str, Any]) -> Certificate:
        """Parse certificate response to model."""
        # Parse scores
        scores = CertificateScores(**data["scores"])

        # Parse safety attestations
        attestations = []
        for att in data.get("safety_attestations", []):
            attestations.append(SafetyAttestation(
                category=att["category"],
                level=att["level"],
                description=att["description"],
                tested_at=datetime.fromisoformat(att["tested_at"]),
                valid=att.get("valid", True),
            ))

        return Certificate(
            id=UUID(data["id"]),
            agent_id=UUID(data["agent_id"]),
            agent_name=data["agent_name"],
            organization_name=data["organization_name"],
            evaluation_id=UUID(data["evaluation_id"]),
            version=data.get("version", "1.0"),
            grade=data["grade"],
            scores=scores,
            capabilities=data.get("capabilities", []),
            not_certified=data.get("not_certified", []),
            safety_attestations=attestations,
            status=CertificateStatus(data["status"]),
            issued_at=datetime.fromisoformat(data["issued_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
            revoked_at=datetime.fromisoformat(data["revoked_at"]) if data.get("revoked_at") else None,
            revocation_reason=data.get("revocation_reason"),
            signature=data["signature"],
            issuer=data.get("issuer", "TrustModel Certificate Authority"),
        )


# Singleton instance
certificates = CertificateClient()


# Convenience functions
async def issue(
    agent: str | UUID,
    evaluation_id: UUID,
    validity_days: int = 365,
) -> Certificate:
    """
    Issue a trust certificate for an agent.

    Args:
        agent: Agent name or ID
        evaluation_id: The evaluation to base the certificate on
        validity_days: How long the certificate is valid

    Returns:
        The issued Certificate
    """
    # Resolve agent ID
    if isinstance(agent, str):
        try:
            agent_id = UUID(agent)
        except ValueError:
            api_client = get_client()
            agents_response = await api_client.list_agents()
            agent_id = None
            for a in agents_response.get("items", []):
                if a["name"] == agent:
                    agent_id = UUID(a["id"])
                    break
            if not agent_id:
                raise CertificateError(f"Agent not found: {agent}")
    else:
        agent_id = agent

    return await certificates.issue(agent_id, evaluation_id, validity_days)


async def verify(certificate_id: UUID | str) -> CertificateVerification:
    """
    Verify a certificate's validity.

    Args:
        certificate_id: The certificate ID to verify

    Returns:
        CertificateVerification with status details
    """
    if isinstance(certificate_id, str):
        certificate_id = UUID(certificate_id)
    return await certificates.verify(certificate_id)


async def revoke(certificate_id: UUID | str, reason: str) -> Certificate:
    """
    Revoke a certificate.

    Args:
        certificate_id: The certificate to revoke
        reason: Reason for revocation

    Returns:
        The revoked Certificate
    """
    if isinstance(certificate_id, str):
        certificate_id = UUID(certificate_id)
    return await certificates.revoke(certificate_id, reason)


async def get_certificate(certificate_id: UUID | str) -> Certificate:
    """
    Get a certificate by ID.

    Args:
        certificate_id: The certificate ID

    Returns:
        The Certificate
    """
    if isinstance(certificate_id, str):
        certificate_id = UUID(certificate_id)
    return await certificates.get(certificate_id)
