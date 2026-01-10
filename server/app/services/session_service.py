"""TACP Session service for agent-to-agent communication."""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.certificate import Certificate, CertificateStatus
from app.models.session import SessionStatus, TACPSession
from app.schemas.session import SessionConstraints, SessionCreate, SessionResponse


class SessionService:
    """Service for TACP session management."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: SessionCreate) -> TACPSession:
        """Create a new TACP session."""
        # Get certificates for both agents
        initiator_cert = await self._get_active_certificate(data.initiator_agent_id)
        responder_cert = await self._get_active_certificate(data.responder_agent_id)

        session = TACPSession(
            initiator_agent_id=data.initiator_agent_id,
            responder_agent_id=data.responder_agent_id,
            initiator_certificate_id=initiator_cert.id if initiator_cert else None,
            responder_certificate_id=responder_cert.id if responder_cert else None,
            status=SessionStatus.PENDING,
            purpose=data.purpose,
            constraints=data.constraints.model_dump(),
            initiator_capabilities=data.requested_capabilities,
        )

        session.add_audit_event(
            "session_initiated",
            {
                "initiator_agent_id": str(data.initiator_agent_id),
                "responder_agent_id": str(data.responder_agent_id),
                "purpose": data.purpose,
            },
        )

        self.db.add(session)
        await self.db.flush()
        return session

    async def get(self, session_id: uuid.UUID) -> Optional[TACPSession]:
        """Get a session by ID."""
        result = await self.db.execute(
            select(TACPSession)
            .where(TACPSession.id == session_id)
            .options(
                joinedload(TACPSession.initiator_agent),
                joinedload(TACPSession.responder_agent),
            )
        )
        return result.scalar_one_or_none()

    async def establish(
        self,
        session_id: uuid.UUID,
        responder_capabilities: List[str],
        agreed_capabilities: List[str],
        scope: Optional[str] = None,
    ) -> Optional[TACPSession]:
        """Establish a session after successful handshake."""
        session = await self.get(session_id)
        if not session:
            return None

        if session.status != SessionStatus.PENDING:
            return None

        session.status = SessionStatus.ESTABLISHED
        session.established_at = datetime.now(timezone.utc)
        session.responder_capabilities = responder_capabilities
        session.agreed_capabilities = agreed_capabilities
        session.scope = scope

        session.add_audit_event(
            "session_established",
            {
                "agreed_capabilities": agreed_capabilities,
                "scope": scope,
            },
        )

        await self.db.flush()
        return session

    async def end(
        self,
        session_id: uuid.UUID,
        reason: str = "completed",
    ) -> Optional[TACPSession]:
        """End a session."""
        session = await self.get(session_id)
        if not session:
            return None

        if session.status == SessionStatus.COMPLETED:
            return session

        session.status = SessionStatus.COMPLETED
        session.ended_at = datetime.now(timezone.utc)
        session.end_reason = reason

        session.add_audit_event("session_ended", {"reason": reason})

        await self.db.flush()
        return session

    async def fail(
        self,
        session_id: uuid.UUID,
        reason: str,
    ) -> Optional[TACPSession]:
        """Mark a session as failed."""
        session = await self.get(session_id)
        if not session:
            return None

        session.status = SessionStatus.FAILED
        session.ended_at = datetime.now(timezone.utc)
        session.end_reason = reason

        session.add_audit_event("error_occurred", {"reason": reason})

        await self.db.flush()
        return session

    async def increment_message_count(self, session_id: uuid.UUID) -> None:
        """Increment the message count for a session."""
        session = await self.get(session_id)
        if session:
            session.message_count += 1
            await self.db.flush()

    async def increment_task_count(self, session_id: uuid.UUID) -> None:
        """Increment the task count for a session."""
        session = await self.get(session_id)
        if session:
            session.task_count += 1
            await self.db.flush()

    async def list_for_agent(
        self,
        agent_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
        status: Optional[SessionStatus] = None,
    ) -> Tuple[List[TACPSession], int]:
        """List sessions for an agent (as initiator or responder)."""
        query = select(TACPSession).where(
            or_(
                TACPSession.initiator_agent_id == agent_id,
                TACPSession.responder_agent_id == agent_id,
            )
        )

        if status:
            query = query.where(TACPSession.status == status)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.scalar(count_query) or 0

        # Get paginated results
        query = (
            query.options(
                joinedload(TACPSession.initiator_agent),
                joinedload(TACPSession.responder_agent),
            )
            .order_by(TACPSession.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(query)
        sessions = list(result.scalars().all())

        return sessions, total

    async def _get_active_certificate(self, agent_id: uuid.UUID) -> Optional[Certificate]:
        """Get the active certificate for an agent."""
        result = await self.db.execute(
            select(Certificate)
            .where(
                Certificate.agent_id == agent_id,
                Certificate.status == CertificateStatus.ACTIVE,
                Certificate.expires_at > datetime.now(timezone.utc),
            )
            .order_by(Certificate.issued_at.desc())
        )
        return result.scalar_one_or_none()

    def to_response(self, session: TACPSession) -> SessionResponse:
        """Convert session model to response schema."""
        return SessionResponse(
            id=session.id,
            initiator_agent_id=session.initiator_agent_id,
            initiator_agent_name=(
                session.initiator_agent.name if session.initiator_agent else None
            ),
            responder_agent_id=session.responder_agent_id,
            responder_agent_name=(
                session.responder_agent.name if session.responder_agent else None
            ),
            initiator_certificate_id=session.initiator_certificate_id,
            responder_certificate_id=session.responder_certificate_id,
            status=session.status,
            purpose=session.purpose,
            scope=session.scope,
            constraints=session.constraints,
            initiator_capabilities=session.initiator_capabilities,
            responder_capabilities=session.responder_capabilities,
            agreed_capabilities=session.agreed_capabilities,
            created_at=session.created_at,
            established_at=session.established_at,
            ended_at=session.ended_at,
            duration_seconds=session.duration_seconds,
            message_count=session.message_count,
            task_count=session.task_count,
            end_reason=session.end_reason,
        )
