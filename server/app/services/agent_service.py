"""Agent service for CRUD operations."""

import uuid
from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.agent import Agent, AgentStatus
from app.models.certificate import Certificate, CertificateStatus
from app.models.evaluation import EvaluationRun
from app.models.trace import Trace
from app.schemas.agent import AgentCreate, AgentResponse, AgentUpdate


class AgentService:
    """Service for agent management operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        data: AgentCreate,
        organization_id: uuid.UUID,
    ) -> Agent:
        """Create a new agent."""
        agent = Agent(
            name=data.name,
            description=data.description,
            agent_type=data.agent_type,
            framework=data.framework,
            version=data.version,
            declared_capabilities=data.declared_capabilities,
            metadata=data.metadata,
            organization_id=organization_id,
        )
        self.db.add(agent)
        await self.db.flush()
        return agent

    async def get(self, agent_id: uuid.UUID) -> Optional[Agent]:
        """Get an agent by ID."""
        result = await self.db.execute(
            select(Agent)
            .where(Agent.id == agent_id)
            .options(joinedload(Agent.organization))
        )
        return result.scalar_one_or_none()

    async def get_by_name(
        self,
        name: str,
        organization_id: uuid.UUID,
    ) -> Optional[Agent]:
        """Get an agent by name within an organization."""
        result = await self.db.execute(
            select(Agent).where(
                Agent.name == name,
                Agent.organization_id == organization_id,
            )
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        organization_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
        status: Optional[AgentStatus] = None,
    ) -> Tuple[List[Agent], int]:
        """List agents for an organization with pagination."""
        query = select(Agent).where(Agent.organization_id == organization_id)

        if status:
            query = query.where(Agent.status == status)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.scalar(count_query) or 0

        # Get paginated results
        query = (
            query.options(joinedload(Agent.organization))
            .order_by(Agent.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(query)
        agents = list(result.scalars().all())

        return agents, total

    async def update(
        self,
        agent_id: uuid.UUID,
        data: AgentUpdate,
    ) -> Optional[Agent]:
        """Update an agent."""
        agent = await self.get(agent_id)
        if not agent:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(agent, field, value)

        await self.db.flush()
        return agent

    async def delete(self, agent_id: uuid.UUID) -> bool:
        """Delete an agent."""
        agent = await self.get(agent_id)
        if not agent:
            return False

        await self.db.delete(agent)
        return True

    async def get_stats(self, agent_id: uuid.UUID) -> dict:
        """Get statistics for an agent."""
        # Trace count
        trace_count = await self.db.scalar(
            select(func.count()).where(Trace.agent_id == agent_id)
        ) or 0

        # Evaluation count
        eval_count = await self.db.scalar(
            select(func.count()).where(EvaluationRun.agent_id == agent_id)
        ) or 0

        # Certificate count
        cert_count = await self.db.scalar(
            select(func.count()).where(Certificate.agent_id == agent_id)
        ) or 0

        # Latest certificate grade
        latest_cert = await self.db.scalar(
            select(Certificate)
            .where(
                Certificate.agent_id == agent_id,
                Certificate.status == CertificateStatus.ACTIVE,
            )
            .order_by(Certificate.issued_at.desc())
        )

        return {
            "trace_count": trace_count,
            "evaluation_count": eval_count,
            "certificate_count": cert_count,
            "latest_certificate_grade": latest_cert.grade if latest_cert else None,
        }

    async def to_response(self, agent: Agent, include_stats: bool = False) -> AgentResponse:
        """Convert agent model to response schema."""
        data = {
            "id": agent.id,
            "name": agent.name,
            "description": agent.description,
            "agent_type": agent.agent_type,
            "framework": agent.framework,
            "version": agent.version,
            "status": agent.status,
            "declared_capabilities": agent.declared_capabilities,
            "metadata": agent.metadata,
            "organization_id": agent.organization_id,
            "organization_name": agent.organization.name if agent.organization else None,
            "created_at": agent.created_at,
            "updated_at": agent.updated_at,
        }

        if include_stats:
            stats = await self.get_stats(agent.id)
            data.update(stats)

        return AgentResponse(**data)
