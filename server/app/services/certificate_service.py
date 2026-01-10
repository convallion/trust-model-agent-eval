"""Certificate service for issuing, verifying, and revoking trust certificates."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.ca.issuer import CertificateIssuer
from app.ca.verifier import CertificateVerifier
from app.config import settings
from app.models.certificate import Certificate, CertificateStatus, Revocation
from app.models.evaluation import EvaluationRun, EvaluationStatus
from app.schemas.certificate import (
    CertificateResponse,
    CertificateVerifyResponse,
    RegistryEntry,
    SafetyAttestation,
)


class CertificateService:
    """Service for certificate management operations."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.issuer = CertificateIssuer()
        self.verifier = CertificateVerifier()

    async def issue(
        self,
        agent_id: uuid.UUID,
        evaluation_id: uuid.UUID,
    ) -> Certificate:
        """Issue a new certificate based on evaluation results."""
        # Get evaluation
        eval_result = await self.db.execute(
            select(EvaluationRun)
            .where(EvaluationRun.id == evaluation_id)
            .options(joinedload(EvaluationRun.agent))
        )
        evaluation = eval_result.scalar_one_or_none()

        if not evaluation:
            raise ValueError("Evaluation not found")

        if evaluation.status != EvaluationStatus.COMPLETED:
            raise ValueError("Evaluation is not completed")

        if not evaluation.certificate_eligible:
            raise ValueError("Evaluation is not eligible for certification")

        if evaluation.agent_id != agent_id:
            raise ValueError("Agent ID mismatch")

        # Revoke any existing active certificates
        await self._revoke_existing_certificates(agent_id, "Superseded by new certificate")

        # Calculate expiry
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=settings.certificate_validity_days
        )

        # Build safety attestations from results
        safety_attestations = self._build_safety_attestations(evaluation.results)

        # Build certified capabilities from results
        certified_capabilities = self._determine_capabilities(evaluation.results)

        # Create certificate
        certificate = Certificate(
            agent_id=agent_id,
            evaluation_id=evaluation_id,
            expires_at=expires_at,
            grade=evaluation.grade.value if evaluation.grade else "F",
            overall_score=float(evaluation.overall_score) if evaluation.overall_score else 0,
            capability_score=(
                float(evaluation.capability_score) if evaluation.capability_score else None
            ),
            safety_score=float(evaluation.safety_score) if evaluation.safety_score else None,
            reliability_score=(
                float(evaluation.reliability_score) if evaluation.reliability_score else None
            ),
            communication_score=(
                float(evaluation.communication_score) if evaluation.communication_score else None
            ),
            certified_capabilities=certified_capabilities,
            not_certified=[],  # TODO: Determine based on failed tests
            safety_attestations=safety_attestations,
            signature="",  # Will be set after signing
        )

        self.db.add(certificate)
        await self.db.flush()

        # Sign the certificate
        signature = await self.issuer.sign(certificate.get_signable_data())
        certificate.signature = signature

        await self.db.flush()
        return certificate

    async def get(self, certificate_id: uuid.UUID) -> Optional[Certificate]:
        """Get a certificate by ID."""
        result = await self.db.execute(
            select(Certificate)
            .where(Certificate.id == certificate_id)
            .options(
                joinedload(Certificate.agent),
                joinedload(Certificate.revocation),
            )
        )
        return result.scalar_one_or_none()

    async def verify(self, certificate_id: uuid.UUID) -> CertificateVerifyResponse:
        """Verify a certificate's validity."""
        certificate = await self.get(certificate_id)

        if not certificate:
            return CertificateVerifyResponse(
                valid=False,
                certificate_id=certificate_id,
                status=CertificateStatus.REVOKED,
                reason="Certificate not found",
                signature_valid=False,
            )

        # Check expiration
        if certificate.is_expired():
            return CertificateVerifyResponse(
                valid=False,
                certificate_id=certificate_id,
                status=CertificateStatus.EXPIRED,
                reason="Certificate has expired",
                signature_valid=True,  # Signature may still be valid
            )

        # Check revocation
        if certificate.status == CertificateStatus.REVOKED:
            reason = certificate.revocation.reason if certificate.revocation else "Revoked"
            return CertificateVerifyResponse(
                valid=False,
                certificate_id=certificate_id,
                status=CertificateStatus.REVOKED,
                reason=reason,
                signature_valid=True,
            )

        # Check suspension
        if certificate.status == CertificateStatus.SUSPENDED:
            return CertificateVerifyResponse(
                valid=False,
                certificate_id=certificate_id,
                status=CertificateStatus.SUSPENDED,
                reason="Certificate is suspended",
                signature_valid=True,
            )

        # Verify signature
        signature_valid = await self.verifier.verify(
            certificate.get_signable_data(),
            certificate.signature,
        )

        if not signature_valid:
            return CertificateVerifyResponse(
                valid=False,
                certificate_id=certificate_id,
                status=certificate.status,
                reason="Invalid signature",
                signature_valid=False,
            )

        # Certificate is valid
        return CertificateVerifyResponse(
            valid=True,
            certificate_id=certificate_id,
            status=certificate.status,
            agent_id=certificate.agent_id,
            agent_name=certificate.agent.name if certificate.agent else None,
            organization_name=(
                certificate.agent.organization.name
                if certificate.agent and certificate.agent.organization
                else None
            ),
            grade=certificate.grade,
            overall_score=float(certificate.overall_score),
            safety_score=float(certificate.safety_score) if certificate.safety_score else None,
            expires_at=certificate.expires_at,
            days_until_expiry=certificate.days_until_expiry(),
            certified_capabilities=certificate.certified_capabilities,
            signature_valid=True,
        )

    async def revoke(
        self,
        certificate_id: uuid.UUID,
        reason: str,
        revoked_by: Optional[uuid.UUID] = None,
    ) -> Optional[Certificate]:
        """Revoke a certificate."""
        certificate = await self.get(certificate_id)
        if not certificate:
            return None

        if certificate.status == CertificateStatus.REVOKED:
            return certificate  # Already revoked

        certificate.status = CertificateStatus.REVOKED

        revocation = Revocation(
            certificate_id=certificate_id,
            reason=reason,
            revoked_by=revoked_by,
        )
        self.db.add(revocation)

        await self.db.flush()
        return certificate

    async def list_for_agent(
        self,
        agent_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
        include_expired: bool = False,
    ) -> Tuple[List[Certificate], int]:
        """List certificates for an agent."""
        query = select(Certificate).where(Certificate.agent_id == agent_id)

        if not include_expired:
            query = query.where(Certificate.status == CertificateStatus.ACTIVE)
            query = query.where(Certificate.expires_at > datetime.now(timezone.utc))

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.scalar(count_query) or 0

        # Get paginated results
        query = (
            query.order_by(Certificate.issued_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(query)
        certificates = list(result.scalars().all())

        return certificates, total

    async def get_registry(
        self,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[RegistryEntry], int]:
        """Get public trust registry of active certificates."""
        query = (
            select(Certificate)
            .where(Certificate.status == CertificateStatus.ACTIVE)
            .where(Certificate.expires_at > datetime.now(timezone.utc))
            .options(joinedload(Certificate.agent))
        )

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.scalar(count_query) or 0

        # Get paginated results
        query = (
            query.order_by(Certificate.overall_score.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(query)
        certificates = list(result.scalars().all())

        entries = []
        for cert in certificates:
            if cert.agent:
                entries.append(
                    RegistryEntry(
                        agent_id=cert.agent_id,
                        agent_name=cert.agent.name,
                        organization_name=(
                            cert.agent.organization.name if cert.agent.organization else "Unknown"
                        ),
                        certificate_id=cert.id,
                        grade=cert.grade,
                        overall_score=float(cert.overall_score),
                        safety_score=float(cert.safety_score) if cert.safety_score else None,
                        certified_capabilities=cert.certified_capabilities,
                        issued_at=cert.issued_at,
                        expires_at=cert.expires_at,
                        status=cert.status,
                    )
                )

        return entries, total

    async def _revoke_existing_certificates(
        self,
        agent_id: uuid.UUID,
        reason: str,
    ) -> None:
        """Revoke all existing active certificates for an agent."""
        result = await self.db.execute(
            select(Certificate).where(
                Certificate.agent_id == agent_id,
                Certificate.status == CertificateStatus.ACTIVE,
            )
        )
        certificates = result.scalars().all()

        for cert in certificates:
            await self.revoke(cert.id, reason)

    def _build_safety_attestations(self, results: dict) -> List[dict]:
        """Build safety attestations from evaluation results."""
        attestations = []
        safety_results = results.get("safety", {}).get("tests", {})

        for test_name, test_data in safety_results.items():
            attestations.append(
                {
                    "type": test_name,
                    "tests_passed": test_data.get("passed", 0),
                    "pass_rate": test_data.get("pass_rate", 0.0),
                }
            )

        return attestations

    def _determine_capabilities(self, results: dict) -> List[str]:
        """Determine certified capabilities from evaluation results."""
        capabilities = []
        capability_results = results.get("capability", {}).get("tests", {})

        # Map test results to capabilities
        capability_map = {
            "task_completion": ["task_execution"],
            "tool_proficiency": ["tool_use"],
            "reasoning_quality": ["reasoning"],
            "code_generation": ["code_generation", "code_review"],
            "file_operations": ["file_operations"],
        }

        for test_name, test_data in capability_results.items():
            score = test_data.get("score", 0)
            if score >= 70 and test_name in capability_map:
                capabilities.extend(capability_map[test_name])

        return list(set(capabilities))

    def to_response(self, certificate: Certificate) -> CertificateResponse:
        """Convert certificate model to response schema."""
        return CertificateResponse(
            id=certificate.id,
            version=certificate.version,
            agent_id=certificate.agent_id,
            agent_name=certificate.agent.name if certificate.agent else None,
            organization_name=(
                certificate.agent.organization.name
                if certificate.agent and certificate.agent.organization
                else None
            ),
            evaluation_id=certificate.evaluation_id,
            status=certificate.status,
            issued_at=certificate.issued_at,
            expires_at=certificate.expires_at,
            days_until_expiry=certificate.days_until_expiry(),
            grade=certificate.grade,
            overall_score=float(certificate.overall_score),
            capability_score=(
                float(certificate.capability_score) if certificate.capability_score else None
            ),
            safety_score=float(certificate.safety_score) if certificate.safety_score else None,
            reliability_score=(
                float(certificate.reliability_score) if certificate.reliability_score else None
            ),
            communication_score=(
                float(certificate.communication_score)
                if certificate.communication_score
                else None
            ),
            certified_capabilities=certificate.certified_capabilities,
            not_certified=certificate.not_certified,
            safety_attestations=[
                SafetyAttestation(**att) for att in certificate.safety_attestations
            ],
            signature=certificate.signature,
            issuer_certificate_id=certificate.issuer_certificate_id,
            created_at=certificate.created_at,
        )
