"""TACP Protocol data models."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class MessageType(str, Enum):
    """Types of TACP messages."""

    # Session management
    session_request = "session_request"
    session_accept = "session_accept"
    session_reject = "session_reject"
    session_end = "session_end"

    # Trust verification
    trust_challenge = "trust_challenge"
    trust_proof = "trust_proof"
    trust_verified = "trust_verified"
    trust_failed = "trust_failed"

    # Capability discovery
    capability_query = "capability_query"
    capability_response = "capability_response"

    # Task delegation
    task_request = "task_request"
    task_accepted = "task_accepted"
    task_rejected = "task_rejected"
    task_progress = "task_progress"
    task_complete = "task_complete"
    task_failed = "task_failed"

    # General
    ping = "ping"
    pong = "pong"
    error = "error"


class SessionStatus(str, Enum):
    """Status of a TACP session."""

    pending = "pending"
    active = "active"
    ended = "ended"
    rejected = "rejected"
    expired = "expired"


class MessageEnvelope(BaseModel):
    """Envelope for all TACP messages."""

    message_id: UUID = Field(default_factory=uuid4)
    message_type: MessageType
    sender_id: UUID
    recipient_id: UUID
    session_id: Optional[UUID] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now())
    payload: dict[str, Any] = Field(default_factory=dict)
    signature: Optional[str] = None
    in_reply_to: Optional[UUID] = None

    def sign(self, private_key: bytes) -> "MessageEnvelope":
        """Sign the message with a private key."""
        from nacl.signing import SigningKey
        import json

        # Create canonical JSON of the message content
        content = {
            "message_id": str(self.message_id),
            "message_type": self.message_type.value,
            "sender_id": str(self.sender_id),
            "recipient_id": str(self.recipient_id),
            "session_id": str(self.session_id) if self.session_id else None,
            "timestamp": self.timestamp.isoformat(),
            "payload": self.payload,
        }
        canonical = json.dumps(content, sort_keys=True, separators=(",", ":"))

        # Sign
        signing_key = SigningKey(private_key)
        signed = signing_key.sign(canonical.encode())
        self.signature = signed.signature.hex()

        return self


class SessionRequest(BaseModel):
    """Request to establish a TACP session."""

    purpose: str = Field(..., min_length=1, max_length=500)
    needed_capabilities: list[str] = Field(default_factory=list)
    constraints: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: int = Field(default=3600, ge=60, le=86400)


class SessionInfo(BaseModel):
    """Information about a TACP session."""

    id: UUID
    initiator_agent_id: UUID
    initiator_agent_name: str
    responder_agent_id: UUID
    responder_agent_name: str
    status: SessionStatus
    purpose: Optional[str] = None
    constraints: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    ended_at: Optional[datetime] = None
    message_count: int = 0


class TrustChallenge(BaseModel):
    """Trust verification challenge."""

    challenge_id: UUID = Field(default_factory=uuid4)
    nonce: str
    required_capabilities: list[str] = Field(default_factory=list)
    minimum_grade: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now())


class TrustProof(BaseModel):
    """Response to a trust challenge."""

    challenge_id: UUID
    certificate_id: UUID
    nonce_signature: str
    certificate_chain: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now())


class CapabilityQuery(BaseModel):
    """Query for agent capabilities."""

    capabilities: list[str] = Field(default_factory=list)
    include_scores: bool = False


class CapabilityResponse(BaseModel):
    """Response to capability query."""

    agent_id: UUID
    agent_name: str
    capabilities: dict[str, bool] = Field(default_factory=dict)
    scores: Optional[dict[str, float]] = None
    certificate_id: Optional[UUID] = None
    certificate_grade: Optional[str] = None


class TaskRequest(BaseModel):
    """Request to delegate a task to another agent."""

    task_id: UUID = Field(default_factory=uuid4)
    task_type: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    constraints: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: Optional[int] = Field(default=300, ge=1, le=3600)
    priority: str = Field(default="normal", pattern="^(low|normal|high|critical)$")


class TaskProgress(BaseModel):
    """Progress update for a delegated task."""

    task_id: UUID
    progress: float = Field(ge=0.0, le=1.0)
    status: str
    message: Optional[str] = None
    intermediate_result: Optional[Any] = None


class TaskResponse(BaseModel):
    """Response/result from a delegated task."""

    task_id: UUID
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    duration_ms: Optional[float] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProtocolError(BaseModel):
    """Error message in TACP protocol."""

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    recoverable: bool = False
