"""TACP Session management endpoints."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.session import SessionStatus
from app.models.user import User
from app.schemas.session import (
    MessageEnvelope,
    SessionCreate,
    SessionListResponse,
    SessionResponse,
)
from app.services.agent_service import AgentService
from app.services.session_service import SessionService

router = APIRouter()


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    data: SessionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    """Create a new TACP session between agents."""
    agent_service = AgentService(db)

    # Verify initiator agent
    initiator = await agent_service.get(data.initiator_agent_id)
    if not initiator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Initiator agent not found",
        )

    if initiator.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create session for this agent",
        )

    # Verify responder agent exists
    responder = await agent_service.get(data.responder_agent_id)
    if not responder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Responder agent not found",
        )

    session_service = SessionService(db)
    session = await session_service.create(data)

    return await session_service.to_response(session)


@router.get("", response_model=SessionListResponse)
async def list_sessions(
    agent_id: Optional[UUID] = None,
    status_filter: Optional[SessionStatus] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionListResponse:
    """List TACP sessions."""
    if not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must belong to an organization",
        )

    # If agent_id provided, verify access
    if agent_id:
        agent_service = AgentService(db)
        agent = await agent_service.get(agent_id)
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent not found",
            )
        if agent.organization_id != current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this agent's sessions",
            )

    session_service = SessionService(db)
    sessions, total = await session_service.list(
        organization_id=current_user.organization_id,
        agent_id=agent_id,
        status=status_filter,
        page=page,
        page_size=page_size,
    )

    items = [await session_service.to_response(s) for s in sessions]

    return SessionListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    """Get session details."""
    session_service = SessionService(db)
    session = await session_service.get(session_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    # Verify access through either agent
    agent_service = AgentService(db)
    initiator = await agent_service.get(session.initiator_agent_id)
    responder = await agent_service.get(session.responder_agent_id)

    can_access = (
        (initiator and initiator.organization_id == current_user.organization_id) or
        (responder and responder.organization_id == current_user.organization_id)
    )

    if not can_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this session",
        )

    return await session_service.to_response(session, include_messages=True)


@router.post("/{session_id}/accept", response_model=SessionResponse)
async def accept_session(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    """Accept a pending session (as responder)."""
    session_service = SessionService(db)
    session = await session_service.get(session_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    # Verify caller owns responder agent
    agent_service = AgentService(db)
    responder = await agent_service.get(session.responder_agent_id)

    if not responder or responder.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to accept this session",
        )

    if session.status != SessionStatus.pending:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot accept session with status '{session.status.value}'",
        )

    session = await session_service.accept(session_id)
    return await session_service.to_response(session)


@router.post("/{session_id}/reject", response_model=SessionResponse)
async def reject_session(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    """Reject a pending session (as responder)."""
    session_service = SessionService(db)
    session = await session_service.get(session_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    # Verify caller owns responder agent
    agent_service = AgentService(db)
    responder = await agent_service.get(session.responder_agent_id)

    if not responder or responder.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to reject this session",
        )

    if session.status != SessionStatus.pending:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reject session with status '{session.status.value}'",
        )

    session = await session_service.reject(session_id)
    return await session_service.to_response(session)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def end_session(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """End an active session."""
    session_service = SessionService(db)
    session = await session_service.get(session_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    # Verify access through either agent
    agent_service = AgentService(db)
    initiator = await agent_service.get(session.initiator_agent_id)
    responder = await agent_service.get(session.responder_agent_id)

    can_access = (
        (initiator and initiator.organization_id == current_user.organization_id) or
        (responder and responder.organization_id == current_user.organization_id)
    )

    if not can_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to end this session",
        )

    await session_service.end(session_id)


@router.post("/{session_id}/messages", response_model=MessageEnvelope)
async def send_message(
    session_id: UUID,
    message: MessageEnvelope,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageEnvelope:
    """Send a message in a session."""
    session_service = SessionService(db)
    session = await session_service.get(session_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    if session.status != SessionStatus.active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session is not active",
        )

    # Verify sender is one of the session agents
    agent_service = AgentService(db)
    sender_agent = await agent_service.get(message.sender_id)

    if not sender_agent or sender_agent.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to send messages as this agent",
        )

    if message.sender_id not in [session.initiator_agent_id, session.responder_agent_id]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sender is not a participant in this session",
        )

    # Store and broadcast message
    stored_message = await session_service.send_message(session_id, message)
    return stored_message


@router.websocket("/{session_id}/ws")
async def session_websocket(
    websocket: WebSocket,
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """WebSocket endpoint for real-time session communication."""
    session_service = SessionService(db)
    session = await session_service.get(session_id)

    if not session:
        await websocket.close(code=4004, reason="Session not found")
        return

    if session.status != SessionStatus.active:
        await websocket.close(code=4003, reason="Session is not active")
        return

    await websocket.accept()

    try:
        # Register connection
        await session_service.register_websocket(session_id, websocket)

        while True:
            # Receive message from WebSocket
            data = await websocket.receive_json()

            try:
                message = MessageEnvelope(**data)

                # Validate sender is participant
                if message.sender_id not in [session.initiator_agent_id, session.responder_agent_id]:
                    await websocket.send_json({
                        "error": "Sender is not a participant in this session"
                    })
                    continue

                # Store and broadcast message
                await session_service.send_message(session_id, message)

            except Exception as e:
                await websocket.send_json({"error": str(e)})

    except WebSocketDisconnect:
        await session_service.unregister_websocket(session_id, websocket)
    except Exception:
        await session_service.unregister_websocket(session_id, websocket)
        raise
