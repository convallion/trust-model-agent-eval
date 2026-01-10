"""Agent data models."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class AgentType(str, Enum):
    """Types of AI agents."""

    coding = "coding"
    research = "research"
    assistant = "assistant"
    orchestrator = "orchestrator"
    specialist = "specialist"
    custom = "custom"


class AgentStatus(str, Enum):
    """Agent registration status."""

    active = "active"
    inactive = "inactive"
    suspended = "suspended"


class AgentCreate(BaseModel):
    """Request to register a new agent."""

    name: str = Field(..., min_length=1, max_length=255)
    agent_type: AgentType = Field(default=AgentType.custom)
    framework: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = Field(default=None, max_length=1000)
    version: Optional[str] = Field(default=None, max_length=50)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentUpdate(BaseModel):
    """Request to update agent details."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    agent_type: Optional[AgentType] = None
    framework: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = Field(default=None, max_length=1000)
    version: Optional[str] = Field(default=None, max_length=50)
    status: Optional[AgentStatus] = None
    metadata: Optional[dict[str, Any]] = None


class AgentStats(BaseModel):
    """Statistics for an agent."""

    total_traces: int = 0
    total_evaluations: int = 0
    latest_certificate_id: Optional[UUID] = None
    latest_certificate_grade: Optional[str] = None
    active_sessions: int = 0


class Agent(BaseModel):
    """Agent representation."""

    id: UUID
    name: str
    agent_type: AgentType
    framework: Optional[str] = None
    description: Optional[str] = None
    version: Optional[str] = None
    status: AgentStatus = AgentStatus.active
    organization_id: UUID
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    stats: Optional[AgentStats] = None

    class Config:
        from_attributes = True

    @property
    def is_active(self) -> bool:
        """Check if agent is active."""
        return self.status == AgentStatus.active

    @property
    def is_certified(self) -> bool:
        """Check if agent has a valid certificate."""
        return self.stats is not None and self.stats.latest_certificate_id is not None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return self.model_dump(mode="json")
