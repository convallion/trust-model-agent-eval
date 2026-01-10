"""TACP Session for agent-to-agent communication."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Callable, Optional
from uuid import UUID, uuid4

import websockets
from websockets.client import WebSocketClientProtocol

from trustmodel.core.config import get_config
from trustmodel.core.exceptions import ProtocolError, SessionError, TrustVerificationError
from trustmodel.core.logging import get_logger
from trustmodel.models.protocol import (
    CapabilityQuery,
    CapabilityResponse,
    MessageEnvelope,
    MessageType,
    SessionStatus,
    TaskProgress,
    TaskRequest,
    TaskResponse,
    TrustChallenge,
    TrustProof,
)

logger = get_logger(__name__)


class TACPSession:
    """
    A TACP session for secure agent-to-agent communication.

    This class manages a WebSocket connection to another agent,
    handles trust verification, and provides methods for
    task delegation and capability queries.
    """

    def __init__(
        self,
        session_id: UUID,
        local_agent_id: UUID,
        remote_agent_id: UUID,
        remote_agent_name: str,
        purpose: str,
        constraints: dict[str, Any],
        ws_url: str,
    ) -> None:
        self.session_id = session_id
        self.local_agent_id = local_agent_id
        self.remote_agent_id = remote_agent_id
        self.remote_agent_name = remote_agent_name
        self.purpose = purpose
        self.constraints = constraints
        self.ws_url = ws_url

        self._ws: Optional[WebSocketClientProtocol] = None
        self._status = SessionStatus.pending
        self._message_handlers: dict[MessageType, Callable[..., Any]] = {}
        self._pending_requests: dict[UUID, asyncio.Future[Any]] = {}
        self._receive_task: Optional[asyncio.Task[None]] = None
        self._trust_verified = False

    @property
    def status(self) -> SessionStatus:
        """Get session status."""
        return self._status

    @property
    def is_active(self) -> bool:
        """Check if session is active."""
        return self._status == SessionStatus.active

    @property
    def is_trusted(self) -> bool:
        """Check if trust has been verified."""
        return self._trust_verified

    async def connect(self) -> None:
        """Connect to the remote agent via WebSocket."""
        if self._ws and not self._ws.closed:
            return

        config = get_config()

        try:
            self._ws = await asyncio.wait_for(
                websockets.connect(self.ws_url),
                timeout=config.websocket_timeout,
            )
            self._status = SessionStatus.active
            self._receive_task = asyncio.create_task(self._receive_loop())

            logger.info(
                "Connected to session",
                session_id=str(self.session_id),
                remote_agent=self.remote_agent_name,
            )

        except asyncio.TimeoutError:
            raise SessionError(
                "Connection timeout",
                session_id=str(self.session_id),
                status="timeout",
            )
        except Exception as e:
            raise SessionError(
                f"Connection failed: {e}",
                session_id=str(self.session_id),
            )

    async def disconnect(self) -> None:
        """Disconnect from the session."""
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass

        if self._ws and not self._ws.closed:
            await self._ws.close()

        self._status = SessionStatus.ended

        logger.info("Disconnected from session", session_id=str(self.session_id))

    async def end(self) -> None:
        """End the session."""
        await self.send_message(MessageType.session_end, {})
        await self.disconnect()

    async def _receive_loop(self) -> None:
        """Background loop for receiving messages."""
        if not self._ws:
            return

        try:
            async for raw_message in self._ws:
                try:
                    data = json.loads(raw_message)
                    message = MessageEnvelope(**data)
                    await self._handle_message(message)
                except Exception as e:
                    logger.error(f"Error handling message: {e}")
        except websockets.ConnectionClosed:
            self._status = SessionStatus.ended
        except Exception as e:
            logger.error(f"Receive loop error: {e}")
            self._status = SessionStatus.ended

    async def _handle_message(self, message: MessageEnvelope) -> None:
        """Handle an incoming message."""
        # Check for response to pending request
        if message.in_reply_to and message.in_reply_to in self._pending_requests:
            future = self._pending_requests.pop(message.in_reply_to)
            future.set_result(message)
            return

        # Check for registered handler
        if message.message_type in self._message_handlers:
            handler = self._message_handlers[message.message_type]
            await handler(message)
            return

        # Default handling
        if message.message_type == MessageType.ping:
            await self.send_message(MessageType.pong, {}, in_reply_to=message.message_id)
        elif message.message_type == MessageType.trust_challenge:
            await self._handle_trust_challenge(message)
        elif message.message_type == MessageType.error:
            logger.error(f"Received error: {message.payload}")

    async def _handle_trust_challenge(self, message: MessageEnvelope) -> None:
        """Handle a trust verification challenge."""
        challenge = TrustChallenge(**message.payload)

        # Get our certificate to prove trust
        from trustmodel.certify import certificates

        try:
            # Get active certificate
            certs, _ = await certificates.list(
                agent_id=self.local_agent_id,
                status=None,
            )

            if not certs:
                await self.send_message(
                    MessageType.trust_failed,
                    {"reason": "No active certificate"},
                    in_reply_to=message.message_id,
                )
                return

            cert = certs[0]

            # Verify we have required capabilities
            if challenge.required_capabilities:
                missing = [
                    cap for cap in challenge.required_capabilities
                    if not cert.has_capability(cap)
                ]
                if missing:
                    await self.send_message(
                        MessageType.trust_failed,
                        {"reason": "Missing capabilities", "missing": missing},
                        in_reply_to=message.message_id,
                    )
                    return

            # Create proof
            proof = TrustProof(
                challenge_id=challenge.challenge_id,
                certificate_id=cert.id,
                nonce_signature="",  # Would be signed with private key
            )

            await self.send_message(
                MessageType.trust_proof,
                proof.model_dump(mode="json"),
                in_reply_to=message.message_id,
            )

        except Exception as e:
            await self.send_message(
                MessageType.trust_failed,
                {"reason": str(e)},
                in_reply_to=message.message_id,
            )

    async def send_message(
        self,
        message_type: MessageType,
        payload: dict[str, Any],
        in_reply_to: Optional[UUID] = None,
    ) -> UUID:
        """Send a message to the remote agent."""
        if not self._ws or self._ws.closed:
            raise SessionError(
                "Not connected",
                session_id=str(self.session_id),
                status="disconnected",
            )

        message = MessageEnvelope(
            message_type=message_type,
            sender_id=self.local_agent_id,
            recipient_id=self.remote_agent_id,
            session_id=self.session_id,
            payload=payload,
            in_reply_to=in_reply_to,
        )

        await self._ws.send(message.model_dump_json())

        return message.message_id

    async def send_and_wait(
        self,
        message_type: MessageType,
        payload: dict[str, Any],
        timeout: float = 30.0,
    ) -> MessageEnvelope:
        """Send a message and wait for response."""
        message_id = await self.send_message(message_type, payload)

        future: asyncio.Future[MessageEnvelope] = asyncio.Future()
        self._pending_requests[message_id] = future

        try:
            response = await asyncio.wait_for(future, timeout=timeout)
            return response
        except asyncio.TimeoutError:
            self._pending_requests.pop(message_id, None)
            raise ProtocolError(
                "Request timeout",
                session_id=str(self.session_id),
                message_type=message_type.value,
                reason="timeout",
            )

    async def verify_trust(
        self,
        required_capabilities: Optional[list[str]] = None,
        minimum_grade: Optional[str] = None,
    ) -> bool:
        """
        Verify trust with the remote agent.

        Args:
            required_capabilities: Capabilities the remote agent must have
            minimum_grade: Minimum certificate grade required

        Returns:
            True if trust is verified

        Raises:
            TrustVerificationError: If verification fails
        """
        import secrets

        challenge = TrustChallenge(
            nonce=secrets.token_hex(32),
            required_capabilities=required_capabilities or [],
            minimum_grade=minimum_grade,
        )

        response = await self.send_and_wait(
            MessageType.trust_challenge,
            challenge.model_dump(mode="json"),
            timeout=30.0,
        )

        if response.message_type == MessageType.trust_verified:
            self._trust_verified = True
            return True

        if response.message_type == MessageType.trust_failed:
            raise TrustVerificationError(
                f"Trust verification failed: {response.payload.get('reason')}",
                agent_id=str(self.remote_agent_id),
                required_capabilities=required_capabilities,
                missing_capabilities=response.payload.get("missing"),
            )

        return False

    async def query_capabilities(
        self,
        capabilities: Optional[list[str]] = None,
        include_scores: bool = False,
    ) -> CapabilityResponse:
        """Query the remote agent's capabilities."""
        query = CapabilityQuery(
            capabilities=capabilities or [],
            include_scores=include_scores,
        )

        response = await self.send_and_wait(
            MessageType.capability_query,
            query.model_dump(mode="json"),
        )

        if response.message_type != MessageType.capability_response:
            raise ProtocolError(
                f"Unexpected response type: {response.message_type}",
                session_id=str(self.session_id),
            )

        return CapabilityResponse(**response.payload)

    async def request_task(
        self,
        task_type: str,
        description: str,
        parameters: Optional[dict[str, Any]] = None,
        timeout: Optional[float] = 300.0,
        on_progress: Optional[Callable[[TaskProgress], None]] = None,
    ) -> TaskResponse:
        """
        Request a task from the remote agent.

        Args:
            task_type: Type of task to perform
            description: Description of the task
            parameters: Task parameters
            timeout: Timeout in seconds
            on_progress: Optional callback for progress updates

        Returns:
            TaskResponse with the result
        """
        task = TaskRequest(
            task_type=task_type,
            description=description,
            parameters=parameters or {},
            timeout_seconds=int(timeout) if timeout else 300,
        )

        # Register progress handler if provided
        if on_progress:
            async def progress_handler(msg: MessageEnvelope) -> None:
                progress = TaskProgress(**msg.payload)
                if progress.task_id == task.task_id:
                    on_progress(progress)

            self._message_handlers[MessageType.task_progress] = progress_handler

        try:
            response = await self.send_and_wait(
                MessageType.task_request,
                task.model_dump(mode="json"),
                timeout=timeout or 300.0,
            )

            if response.message_type == MessageType.task_rejected:
                raise ProtocolError(
                    f"Task rejected: {response.payload.get('reason')}",
                    session_id=str(self.session_id),
                    message_type="task_rejected",
                )

            if response.message_type == MessageType.task_failed:
                raise ProtocolError(
                    f"Task failed: {response.payload.get('error')}",
                    session_id=str(self.session_id),
                    message_type="task_failed",
                )

            return TaskResponse(**response.payload)

        finally:
            self._message_handlers.pop(MessageType.task_progress, None)

    def on_message(
        self,
        message_type: MessageType,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator to register a message handler."""
        def decorator(handler: Callable[..., Any]) -> Callable[..., Any]:
            self._message_handlers[message_type] = handler
            return handler
        return decorator

    async def __aenter__(self) -> "TACPSession":
        await self.connect()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.end()
