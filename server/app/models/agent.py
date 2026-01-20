"""Agent model for registered AI agents."""

import uuid
from enum import Enum
from typing import TYPE_CHECKING, Any, List, Optional

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.certificate import Certificate
    from app.models.evaluation import EvaluationRun
    from app.models.session import TACPSession
    from app.models.trace import Trace
    from app.models.user import Organization


class AgentType(str, Enum):
    """Types of AI agents."""

    CODING = "coding"
    CONVERSATIONAL = "conversational"
    RESEARCH = "research"
    ANALYSIS = "analysis"
    AUTOMATION = "automation"
    CUSTOM = "custom"


class AgentStatus(str, Enum):
    """Agent registration status."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class Agent(Base, UUIDMixin, TimestampMixin):
    """Registered AI agent that can be evaluated and certified."""

    __tablename__ = "agents"

    # Basic info
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    agent_type: Mapped[AgentType] = mapped_column(
        String(50),
        nullable=False,
        default=AgentType.CUSTOM,
    )
    framework: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Agent framework (e.g., LangChain, AutoGen, Claude Code)",
    )
    version: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Agent version string",
    )

    # Status
    status: Mapped[AgentStatus] = mapped_column(
        String(20),
        nullable=False,
        default=AgentStatus.ACTIVE,
    )

    # Metadata (using agent_metadata as 'metadata' is reserved by SQLAlchemy)
    agent_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )

    # Capabilities declared by the agent
    declared_capabilities: Mapped[List[str]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
    )

    # Public key for TACP protocol signing (Ed25519, hex-encoded)
    public_key: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        comment="Ed25519 public key for message signing (hex-encoded)",
    )

    # Organization relationship
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="agents",
    )

    # Relationships
    traces: Mapped[List["Trace"]] = relationship(
        "Trace",
        back_populates="agent",
        cascade="all, delete-orphan",
    )
    evaluations: Mapped[List["EvaluationRun"]] = relationship(
        "EvaluationRun",
        back_populates="agent",
        cascade="all, delete-orphan",
    )
    certificates: Mapped[List["Certificate"]] = relationship(
        "Certificate",
        back_populates="agent",
        cascade="all, delete-orphan",
    )
    initiated_sessions: Mapped[List["TACPSession"]] = relationship(
        "TACPSession",
        back_populates="initiator_agent",
        foreign_keys="TACPSession.initiator_agent_id",
    )
    received_sessions: Mapped[List["TACPSession"]] = relationship(
        "TACPSession",
        back_populates="responder_agent",
        foreign_keys="TACPSession.responder_agent_id",
    )

    @property
    def registry_path(self) -> str:
        """Get the registry path for this agent."""
        return f"{self.organization.name}/{self.name}"
