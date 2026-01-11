"""TACP Session schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.session import SessionStatus


class SessionConstraints(BaseModel):
    """Constraints for a TACP session."""

    max_duration_minutes: int = Field(default=60, ge=1, le=1440)
    max_messages: int = Field(default=100, ge=1, le=10000)
    max_tasks: int = Field(default=10, ge=1, le=100)
    data_classification: str = Field(
        default="internal",
        pattern="^(public|internal|confidential)$",
    )
    allowed_task_types: List[str] = Field(default_factory=list)


class SessionCreate(BaseModel):
    """Request to create a TACP session."""

    initiator_agent_id: UUID
    responder_agent_id: UUID
    purpose: str = Field(..., min_length=1, max_length=1000)
    requested_capabilities: List[str] = Field(default_factory=list)
    constraints: SessionConstraints = Field(default_factory=SessionConstraints)


class SessionResponse(BaseModel):
    """TACP session response."""

    id: UUID
    initiator_agent_id: UUID
    initiator_agent_name: Optional[str] = None
    responder_agent_id: UUID
    responder_agent_name: Optional[str] = None
    initiator_certificate_id: Optional[UUID]
    responder_certificate_id: Optional[UUID]
    status: SessionStatus
    purpose: Optional[str]
    scope: Optional[str]
    constraints: Dict[str, Any]

    # Capabilities
    initiator_capabilities: List[str]
    responder_capabilities: List[str]
    agreed_capabilities: List[str]

    # Timing
    created_at: datetime
    established_at: Optional[datetime]
    ended_at: Optional[datetime]
    duration_seconds: Optional[int]

    # Stats
    message_count: int
    task_count: int

    # Termination
    end_reason: Optional[str]

    model_config = {"from_attributes": True}


class SessionListResponse(BaseModel):
    """Paginated list of sessions."""

    items: List[SessionResponse]
    total: int
    page: int
    page_size: int
    pages: int


class MessageEnvelope(BaseModel):
    """TACP message envelope."""

    protocol_version: str = "TACP/1.0"
    message_id: Optional[UUID] = None  # Auto-generated if not provided
    timestamp: Optional[datetime] = None  # Auto-set if not provided
    sender_id: UUID  # The sending agent's ID
    sender_certificate_id: Optional[UUID] = None  # May not have certificate
    recipient_id: UUID  # The receiving agent's ID
    message_type: str  # "task_request", "task_response", "status", "error"
    payload: Dict[str, Any] = Field(default_factory=dict)
    signature: Optional[str] = None  # Optional signature for verification


class TaskRequest(BaseModel):
    """Request for a task within a session."""

    task_id: UUID
    task_type: str
    description: str
    inputs: Dict[str, Any] = Field(default_factory=dict)
    expected_output_format: Optional[Dict[str, Any]] = None
    timeout_seconds: int = Field(default=60, ge=1, le=3600)


class TaskResponse(BaseModel):
    """Response to a task request."""

    task_id: UUID
    status: str = Field(pattern="^(completed|failed|partial)$")
    outputs: Dict[str, Any] = Field(default_factory=dict)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    sources: List[str] = Field(default_factory=list)
    error: Optional[str] = None
