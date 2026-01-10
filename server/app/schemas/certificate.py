"""Certificate schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.certificate import CertificateStatus


class SafetyAttestation(BaseModel):
    """A safety attestation in a certificate."""

    type: str
    tests_passed: int
    pass_rate: float


class CertificateIssueRequest(BaseModel):
    """Request to issue a certificate."""

    agent_id: UUID
    evaluation_id: UUID


class CertificateResponse(BaseModel):
    """Certificate information response."""

    id: UUID
    version: str
    agent_id: UUID
    agent_name: Optional[str] = None
    organization_name: Optional[str] = None
    evaluation_id: UUID
    status: CertificateStatus
    issued_at: datetime
    expires_at: datetime
    days_until_expiry: int

    # Scores
    grade: str
    overall_score: float
    capability_score: Optional[float]
    safety_score: Optional[float]
    reliability_score: Optional[float]
    communication_score: Optional[float]

    # Capabilities
    certified_capabilities: List[str]
    not_certified: List[str]

    # Safety
    safety_attestations: List[SafetyAttestation]

    # Signature
    signature: str
    issuer_certificate_id: Optional[UUID]

    # Timestamps
    created_at: datetime

    model_config = {"from_attributes": True}


class CertificateVerifyResponse(BaseModel):
    """Response from certificate verification."""

    valid: bool
    certificate_id: UUID
    status: CertificateStatus
    reason: Optional[str] = Field(
        default=None,
        description="Reason if certificate is invalid",
    )

    # If valid, include summary info
    agent_id: Optional[UUID] = None
    agent_name: Optional[str] = None
    organization_name: Optional[str] = None
    grade: Optional[str] = None
    overall_score: Optional[float] = None
    safety_score: Optional[float] = None
    expires_at: Optional[datetime] = None
    days_until_expiry: Optional[int] = None
    certified_capabilities: Optional[List[str]] = None

    # Signature verification
    signature_valid: bool = False


class CertificateRevokeRequest(BaseModel):
    """Request to revoke a certificate."""

    reason: str = Field(..., min_length=10, max_length=1000)


class CertificateListResponse(BaseModel):
    """Paginated list of certificates."""

    items: List[CertificateResponse]
    total: int
    page: int
    page_size: int
    pages: int


class RegistryEntry(BaseModel):
    """Public trust registry entry."""

    agent_id: UUID
    agent_name: str
    organization_name: str
    certificate_id: UUID
    grade: str
    overall_score: float
    safety_score: Optional[float]
    certified_capabilities: List[str]
    issued_at: datetime
    expires_at: datetime
    status: CertificateStatus


class RegistryResponse(BaseModel):
    """Public trust registry response."""

    entries: List[RegistryEntry]
    total: int
    page: int
    page_size: int
    pages: int
