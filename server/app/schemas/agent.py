"""Agent schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.agent import AgentStatus, AgentType


class AgentCreate(BaseModel):
    """Request to register a new agent."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    agent_type: AgentType = AgentType.CUSTOM
    framework: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Agent framework (e.g., LangChain, AutoGen, Claude Code)",
    )
    version: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Agent version string",
    )
    declared_capabilities: List[str] = Field(
        default_factory=list,
        description="Capabilities this agent claims to have",
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentUpdate(BaseModel):
    """Request to update an agent."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    agent_type: Optional[AgentType] = None
    framework: Optional[str] = None
    version: Optional[str] = None
    status: Optional[AgentStatus] = None
    declared_capabilities: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class AgentResponse(BaseModel):
    """Agent information response."""

    id: UUID
    name: str
    description: Optional[str]
    agent_type: AgentType
    framework: Optional[str]
    version: Optional[str]
    status: AgentStatus
    declared_capabilities: List[str]
    metadata: Dict[str, Any]
    organization_id: UUID
    organization_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    # Stats (optional, may not always be included)
    trace_count: Optional[int] = None
    evaluation_count: Optional[int] = None
    certificate_count: Optional[int] = None
    latest_certificate_grade: Optional[str] = None

    model_config = {"from_attributes": True}


class AgentListResponse(BaseModel):
    """Paginated list of agents."""

    items: List[AgentResponse]
    total: int
    page: int
    page_size: int
    pages: int
