"""TACP Session model for agent-to-agent communication."""

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.agent import Agent


class SessionStatus(str, Enum):
    """Status of a TACP session."""

    PENDING = "pending"  # Handshake in progress
    ESTABLISHED = "established"  # Session active
    COMPLETED = "completed"  # Clean termination
    FAILED = "failed"  # Handshake failed
    TIMEOUT = "timeout"  # Session timed out
    TERMINATED = "terminated"  # Force terminated


class TACPSession(Base, UUIDMixin, TimestampMixin):
    """
    TrustModel Agent Communication Protocol (TACP) session.

    Represents a communication session between two certified agents.
    """

    __tablename__ = "tacp_sessions"

    # Initiator agent (the one who started the session)
    initiator_agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    initiator_agent: Mapped["Agent"] = relationship(
        "Agent",
        back_populates="initiated_sessions",
        foreign_keys=[initiator_agent_id],
    )

    # Responder agent (the one being contacted)
    responder_agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    responder_agent: Mapped["Agent"] = relationship(
        "Agent",
        back_populates="received_sessions",
        foreign_keys=[responder_agent_id],
    )

    # Certificate IDs used for verification
    initiator_certificate_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    responder_certificate_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    # Status
    status: Mapped[SessionStatus] = mapped_column(
        String(20),
        default=SessionStatus.PENDING,
        nullable=False,
        index=True,
    )

    # Session details
    purpose: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Purpose of this session",
    )
    scope: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Agreed scope of collaboration",
    )

    # Constraints
    constraints: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        comment="Session constraints (max_duration, max_messages, data_classification)",
    )

    # Capabilities exchanged
    initiator_capabilities: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
    )
    responder_capabilities: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
    )
    agreed_capabilities: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        comment="Capabilities agreed upon for this session",
    )

    # Timing
    established_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Termination reason
    end_reason: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Reason for session end (completed, timeout, error, user_cancelled)",
    )

    # Message counts
    message_count: Mapped[int] = mapped_column(default=0, nullable=False)
    task_count: Mapped[int] = mapped_column(default=0, nullable=False)

    # Audit trail
    audit_log: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        comment="Audit log of significant session events",
    )

    @property
    def duration_seconds(self) -> Optional[int]:
        """Calculate session duration in seconds."""
        if self.ended_at and self.established_at:
            delta = self.ended_at - self.established_at
            return int(delta.total_seconds())
        return None

    def add_audit_event(self, event_type: str, details: dict[str, Any]) -> None:
        """Add an event to the audit log."""
        event = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "details": details,
        }
        self.audit_log = self.audit_log + [event]


# ═══════════════════════════════════════════════════════════════════════════════
# Constraints Schema (for documentation)
# ═══════════════════════════════════════════════════════════════════════════════

# constraints = {
#     "max_duration_minutes": 60,
#     "max_messages": 100,
#     "max_tasks": 10,
#     "data_classification": "internal",  # public, internal, confidential
#     "allowed_task_types": ["research", "summarize"],
# }

# ═══════════════════════════════════════════════════════════════════════════════
# Audit Log Event Types
# ═══════════════════════════════════════════════════════════════════════════════

# - session_initiated
# - certificate_verified
# - capabilities_exchanged
# - session_established
# - task_requested
# - task_completed
# - message_sent
# - message_received
# - session_ended
# - error_occurred
