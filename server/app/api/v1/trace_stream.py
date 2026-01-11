"""WebSocket endpoint for real-time trace streaming."""

import asyncio
import json
from datetime import datetime, timezone
from typing import Dict, Set
from uuid import UUID

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.database import async_session_maker
from app.models.user import User

router = APIRouter()


class TraceStreamManager:
    """Manages WebSocket connections for trace streaming."""

    def __init__(self):
        # Map of user_id -> set of websockets
        self.connections: Dict[str, Set[WebSocket]] = {}
        # Map of organization_id -> set of user_ids
        self.org_users: Dict[str, Set[str]] = {}

    async def connect(self, websocket: WebSocket, user_id: str, org_id: str):
        """Register a new WebSocket connection."""
        await websocket.accept()

        if user_id not in self.connections:
            self.connections[user_id] = set()
        self.connections[user_id].add(websocket)

        if org_id not in self.org_users:
            self.org_users[org_id] = set()
        self.org_users[org_id].add(user_id)

    def disconnect(self, websocket: WebSocket, user_id: str, org_id: str):
        """Remove a WebSocket connection."""
        if user_id in self.connections:
            self.connections[user_id].discard(websocket)
            if not self.connections[user_id]:
                del self.connections[user_id]

        if org_id in self.org_users:
            # Only remove user from org if they have no more connections
            if user_id not in self.connections:
                self.org_users[org_id].discard(user_id)
                if not self.org_users[org_id]:
                    del self.org_users[org_id]

    async def broadcast_to_org(self, org_id: str, message: dict):
        """Broadcast a trace event to all users in an organization."""
        if org_id not in self.org_users:
            return

        disconnected = []
        for user_id in self.org_users[org_id]:
            if user_id in self.connections:
                for ws in self.connections[user_id].copy():
                    try:
                        await ws.send_json(message)
                    except Exception:
                        disconnected.append((ws, user_id))

        # Clean up disconnected websockets
        for ws, user_id in disconnected:
            if user_id in self.connections:
                self.connections[user_id].discard(ws)


# Global stream manager
stream_manager = TraceStreamManager()


async def get_user_from_token(token: str) -> tuple[str, str] | None:
    """Validate token and return (user_id, org_id)."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id = payload.get("sub")
        if not user_id:
            return None

        async with async_session_maker() as db:
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if not user or not user.organization_id:
                return None
            return str(user.id), str(user.organization_id)
    except JWTError:
        return None


@router.websocket("/stream")
async def trace_stream_websocket(
    websocket: WebSocket,
    token: str = Query(...),
):
    """
    WebSocket endpoint for real-time trace streaming.

    Clients connect with their auth token and receive trace events
    for their organization in real-time.

    Events sent to client:
    - trace_started: New trace begun
    - span_added: New span added to trace
    - trace_completed: Trace finished
    - trace_error: Error in trace
    """
    # Authenticate
    auth_result = await get_user_from_token(token)
    if not auth_result:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    user_id, org_id = auth_result

    await stream_manager.connect(websocket, user_id, org_id)

    try:
        # Send connection confirmation
        await websocket.send_json({
            "type": "connected",
            "message": "Connected to trace stream",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # Keep connection alive and handle any client messages
        while True:
            try:
                # Wait for client messages (ping/pong or commands)
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0  # Send ping every 30s
                )

                try:
                    message = json.loads(data)
                    if message.get("type") == "ping":
                        await websocket.send_json({"type": "pong"})
                except json.JSONDecodeError:
                    pass

            except asyncio.TimeoutError:
                # Send keepalive ping
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break

    except WebSocketDisconnect:
        pass
    finally:
        stream_manager.disconnect(websocket, user_id, org_id)


async def emit_trace_event(org_id: str, event_type: str, data: dict):
    """Emit a trace event to all connected clients in an organization."""
    message = {
        "type": event_type,
        "data": data,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    await stream_manager.broadcast_to_org(org_id, message)


# Helper functions to be called from trace ingestion
async def notify_trace_started(org_id: str, trace_id: str, agent_id: str, agent_name: str):
    """Notify clients that a new trace has started."""
    await emit_trace_event(org_id, "trace_started", {
        "trace_id": trace_id,
        "agent_id": agent_id,
        "agent_name": agent_name,
    })


async def notify_span_added(
    org_id: str,
    trace_id: str,
    span_id: str,
    span_type: str,
    name: str,
    status: str,
    attributes: dict = None,
):
    """Notify clients that a new span was added."""
    await emit_trace_event(org_id, "span_added", {
        "trace_id": trace_id,
        "span_id": span_id,
        "span_type": span_type,
        "name": name,
        "status": status,
        "attributes": attributes or {},
    })


async def notify_trace_completed(org_id: str, trace_id: str, success: bool, duration_ms: int = None):
    """Notify clients that a trace has completed."""
    await emit_trace_event(org_id, "trace_completed", {
        "trace_id": trace_id,
        "success": success,
        "duration_ms": duration_ms,
    })
