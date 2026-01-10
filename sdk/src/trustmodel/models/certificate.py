"""Certificate data models."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CertificateStatus(str, Enum):
    """Status of a trust certificate."""

    active = "active"
    expired = "expired"
    revoked = "revoked"
    suspended = "suspended"


class SafetyAttestation(BaseModel):
    """Safety attestation within a certificate."""

    category: str
    level: str = Field(description="low, medium, high")
    description: str
    tested_at: datetime
    valid: bool = True


class CertificateScores(BaseModel):
    """Score breakdown in a certificate."""

    overall: float = Field(ge=0.0, le=100.0)
    capability: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    safety: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    reliability: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    communication: Optional[float] = Field(default=None, ge=0.0, le=100.0)


class Certificate(BaseModel):
    """Trust certificate representation."""

    id: UUID
    agent_id: UUID
    agent_name: str
    organization_name: str
    evaluation_id: UUID
    version: str = "1.0"
    grade: str = Field(pattern="^[A-F]$")
    scores: CertificateScores
    capabilities: list[str] = Field(default_factory=list)
    not_certified: list[str] = Field(default_factory=list)
    safety_attestations: list[SafetyAttestation] = Field(default_factory=list)
    status: CertificateStatus = CertificateStatus.active
    issued_at: datetime
    expires_at: datetime
    revoked_at: Optional[datetime] = None
    revocation_reason: Optional[str] = None
    signature: str
    issuer: str = "TrustModel Certificate Authority"

    class Config:
        from_attributes = True

    @property
    def is_valid(self) -> bool:
        """Check if certificate is currently valid."""
        if self.status != CertificateStatus.active:
            return False
        return datetime.now(self.expires_at.tzinfo) < self.expires_at

    @property
    def is_expired(self) -> bool:
        """Check if certificate has expired."""
        return datetime.now(self.expires_at.tzinfo) >= self.expires_at

    @property
    def is_revoked(self) -> bool:
        """Check if certificate has been revoked."""
        return self.status == CertificateStatus.revoked

    @property
    def days_until_expiry(self) -> int:
        """Calculate days until expiration."""
        if self.is_expired:
            return 0
        delta = self.expires_at - datetime.now(self.expires_at.tzinfo)
        return max(0, delta.days)

    def has_capability(self, capability: str) -> bool:
        """Check if agent is certified for a capability."""
        return capability.lower() in [c.lower() for c in self.capabilities]

    def to_public_dict(self) -> dict[str, Any]:
        """Convert to public-safe dictionary (excludes signature)."""
        data = self.model_dump(mode="json")
        del data["signature"]
        return data


class CertificateVerification(BaseModel):
    """Result of certificate verification."""

    certificate_id: UUID
    valid: bool
    status: CertificateStatus
    signature_valid: bool
    not_expired: bool
    not_revoked: bool
    agent_id: UUID
    agent_name: str
    grade: str
    capabilities: list[str] = Field(default_factory=list)
    issued_at: datetime
    expires_at: datetime
    verified_at: datetime
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @property
    def is_fully_valid(self) -> bool:
        """Check if all verification checks passed."""
        return self.valid and self.signature_valid and self.not_expired and self.not_revoked


class CertificateIssueRequest(BaseModel):
    """Request to issue a new certificate."""

    agent_id: UUID
    evaluation_id: UUID
    validity_days: int = Field(default=365, ge=1, le=730)


class CertificateRevokeRequest(BaseModel):
    """Request to revoke a certificate."""

    reason: str = Field(..., min_length=1, max_length=500)


class CertificateChain(BaseModel):
    """Certificate chain for verification."""

    certificate: Certificate
    issuer_certificate: Optional[str] = None
    root_certificate: str
    chain_valid: bool = True
