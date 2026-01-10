"""Trust Certificate and Revocation models."""

import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, List, Optional

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.agent import Agent
    from app.models.evaluation import EvaluationRun


class CertificateStatus(str, Enum):
    """Status of a trust certificate."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    EXPIRED = "expired"


class Certificate(Base, UUIDMixin, TimestampMixin):
    """
    Trust Certificate issued to an agent after successful evaluation.

    This is the core of the TrustModel system - the "SSL certificate" for agents.
    """

    __tablename__ = "certificates"

    # Version
    version: Mapped[str] = mapped_column(
        String(10),
        default="1.0",
        nullable=False,
    )

    # Agent relationship
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent: Mapped["Agent"] = relationship("Agent", back_populates="certificates")

    # Evaluation relationship
    evaluation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evaluation_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    evaluation: Mapped["EvaluationRun"] = relationship(
        "EvaluationRun",
        back_populates="certificate",
    )

    # Status and validity
    status: Mapped[CertificateStatus] = mapped_column(
        String(20),
        default=CertificateStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    # Scores (copied from evaluation for quick access)
    grade: Mapped[str] = mapped_column(String(1), nullable=False)
    overall_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    capability_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    safety_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    reliability_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    communication_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)

    # Capabilities
    certified_capabilities: Mapped[List[str]] = mapped_column(
        ARRAY(String),
        default=list,
        nullable=False,
        comment="Capabilities this agent is certified for",
    )
    not_certified: Mapped[List[str]] = mapped_column(
        ARRAY(String),
        default=list,
        nullable=False,
        comment="Explicitly NOT certified for these capabilities",
    )

    # Safety attestations
    safety_attestations: Mapped[List[dict[str, Any]]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        comment="List of safety attestations with test counts and pass rates",
    )

    # Cryptographic signature
    signature: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Ed25519 signature of certificate data",
    )
    issuer_certificate_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="ID of the issuing CA certificate (for chain of trust)",
    )

    # Revocation relationship
    revocation: Mapped[Optional["Revocation"]] = relationship(
        "Revocation",
        back_populates="certificate",
        uselist=False,
    )

    def is_valid(self) -> bool:
        """Check if certificate is currently valid."""
        if self.status != CertificateStatus.ACTIVE:
            return False
        if datetime.now(timezone.utc) > self.expires_at:
            return False
        return True

    def is_expired(self) -> bool:
        """Check if certificate has expired."""
        return datetime.now(timezone.utc) > self.expires_at

    def days_until_expiry(self) -> int:
        """Get number of days until certificate expires."""
        delta = self.expires_at - datetime.now(timezone.utc)
        return max(0, delta.days)

    def get_signable_data(self) -> dict[str, Any]:
        """Get the data that should be signed for this certificate."""
        return {
            "certificate_id": str(self.id),
            "version": self.version,
            "agent_id": str(self.agent_id),
            "evaluation_id": str(self.evaluation_id),
            "issued_at": self.issued_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "grade": self.grade,
            "overall_score": float(self.overall_score),
            "capability_score": float(self.capability_score) if self.capability_score else None,
            "safety_score": float(self.safety_score) if self.safety_score else None,
            "reliability_score": float(self.reliability_score) if self.reliability_score else None,
            "communication_score": (
                float(self.communication_score) if self.communication_score else None
            ),
            "certified_capabilities": self.certified_capabilities,
            "not_certified": self.not_certified,
            "safety_attestations": self.safety_attestations,
        }


class Revocation(Base, UUIDMixin, TimestampMixin):
    """Revocation record for a certificate."""

    __tablename__ = "revocations"

    # Certificate relationship
    certificate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("certificates.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    certificate: Mapped["Certificate"] = relationship(
        "Certificate",
        back_populates="revocation",
    )

    # Revocation details
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    revoked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    revoked_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="User ID who initiated the revocation",
    )
