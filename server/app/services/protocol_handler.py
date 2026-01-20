"""TACP Protocol message handlers for server-side processing."""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Coroutine, Optional
from uuid import UUID, uuid4

import structlog
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError

from app.models.session import SessionStatus

logger = structlog.get_logger()


class MessageType(str, Enum):
    """TACP message types."""

    # Session lifecycle
    SESSION_INIT = "session_init"
    SESSION_ACCEPT = "session_accept"
    SESSION_REJECT = "session_reject"
    SESSION_END = "session_end"

    # Trust verification
    TRUST_CHALLENGE = "trust_challenge"
    TRUST_PROOF = "trust_proof"
    TRUST_VERIFIED = "trust_verified"
    TRUST_FAILED = "trust_failed"

    # Capability exchange
    CAPABILITY_QUERY = "capability_query"
    CAPABILITY_RESPONSE = "capability_response"

    # Task delegation
    TASK_REQUEST = "task_request"
    TASK_ACCEPT = "task_accept"
    TASK_REJECT = "task_reject"
    TASK_PROGRESS = "task_progress"
    TASK_COMPLETE = "task_complete"
    TASK_FAILED = "task_failed"

    # Utility
    PING = "ping"
    PONG = "pong"
    ERROR = "error"


@dataclass
class TACPMessage:
    """A TACP protocol message."""

    message_type: MessageType
    sender_id: UUID
    recipient_id: UUID
    session_id: UUID
    payload: dict[str, Any] = field(default_factory=dict)
    message_id: UUID = field(default_factory=uuid4)
    in_reply_to: Optional[UUID] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    signature: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TACPMessage":
        """Create from dictionary."""
        return cls(
            message_type=MessageType(data["message_type"]),
            sender_id=UUID(data["sender_id"]),
            recipient_id=UUID(data["recipient_id"]),
            session_id=UUID(data["session_id"]),
            payload=data.get("payload", {}),
            message_id=UUID(data.get("message_id", str(uuid4()))),
            in_reply_to=UUID(data["in_reply_to"]) if data.get("in_reply_to") else None,
            timestamp=datetime.fromisoformat(data["timestamp"]) if data.get("timestamp") else datetime.now(timezone.utc),
            signature=data.get("signature"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "message_type": self.message_type.value,
            "sender_id": str(self.sender_id),
            "recipient_id": str(self.recipient_id),
            "session_id": str(self.session_id),
            "payload": self.payload,
            "message_id": str(self.message_id),
            "in_reply_to": str(self.in_reply_to) if self.in_reply_to else None,
            "timestamp": self.timestamp.isoformat(),
            "signature": self.signature,
        }


@dataclass
class TrustChallenge:
    """Trust verification challenge."""

    challenge_id: UUID = field(default_factory=uuid4)
    nonce: str = field(default_factory=lambda: secrets.token_hex(32))
    required_capabilities: list[str] = field(default_factory=list)
    minimum_grade: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "challenge_id": str(self.challenge_id),
            "nonce": self.nonce,
            "required_capabilities": self.required_capabilities,
            "minimum_grade": self.minimum_grade,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class TrustProof:
    """Trust verification proof."""

    challenge_id: UUID
    certificate_id: UUID
    nonce_signature: str
    capabilities: list[str] = field(default_factory=list)
    grade: Optional[str] = None
    valid_until: Optional[datetime] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TrustProof":
        return cls(
            challenge_id=UUID(data["challenge_id"]),
            certificate_id=UUID(data["certificate_id"]),
            nonce_signature=data["nonce_signature"],
            capabilities=data.get("capabilities", []),
            grade=data.get("grade"),
            valid_until=datetime.fromisoformat(data["valid_until"]) if data.get("valid_until") else None,
        )


MessageHandler = Callable[[TACPMessage], Coroutine[Any, Any, Optional[TACPMessage]]]


class ProtocolHandler:
    """
    Server-side TACP protocol handler.

    Processes incoming messages and generates appropriate responses.
    """

    def __init__(
        self,
        session_service: Any,
        certificate_service: Any,
        agent_service: Any,
    ) -> None:
        """
        Initialize the protocol handler.

        Args:
            session_service: Service for session management
            certificate_service: Service for certificate operations
            agent_service: Service for agent operations
        """
        self.session_service = session_service
        self.certificate_service = certificate_service
        self.agent_service = agent_service

        # Pending trust challenges (challenge_id -> TrustChallenge)
        self._pending_challenges: dict[UUID, TrustChallenge] = {}

        # Message handlers
        self._handlers: dict[MessageType, MessageHandler] = {
            MessageType.TRUST_CHALLENGE: self._handle_trust_challenge,
            MessageType.TRUST_PROOF: self._handle_trust_proof,
            MessageType.CAPABILITY_QUERY: self._handle_capability_query,
            MessageType.TASK_REQUEST: self._handle_task_request,
            MessageType.TASK_PROGRESS: self._handle_task_progress,
            MessageType.TASK_COMPLETE: self._handle_task_complete,
            MessageType.TASK_FAILED: self._handle_task_failed,
            MessageType.PING: self._handle_ping,
            MessageType.SESSION_END: self._handle_session_end,
        }

    async def handle_message(self, message: TACPMessage) -> Optional[TACPMessage]:
        """
        Handle an incoming TACP message.

        Args:
            message: The incoming message

        Returns:
            Optional response message
        """
        handler = self._handlers.get(message.message_type)

        if not handler:
            logger.warning(
                "No handler for message type",
                message_type=message.message_type.value,
            )
            return self._create_error_response(
                message,
                f"Unknown message type: {message.message_type.value}",
            )

        try:
            return await handler(message)
        except Exception as e:
            logger.error(
                "Error handling message",
                message_type=message.message_type.value,
                error=str(e),
                exc_info=True,
            )
            return self._create_error_response(message, str(e))

    async def _handle_trust_challenge(self, message: TACPMessage) -> Optional[TACPMessage]:
        """Handle a trust verification challenge."""
        challenge = TrustChallenge(
            nonce=message.payload.get("nonce", secrets.token_hex(32)),
            required_capabilities=message.payload.get("required_capabilities", []),
            minimum_grade=message.payload.get("minimum_grade"),
        )

        # Store challenge for later verification
        self._pending_challenges[challenge.challenge_id] = challenge

        logger.info(
            "Trust challenge created",
            challenge_id=str(challenge.challenge_id),
            required_capabilities=challenge.required_capabilities,
        )

        # Get the recipient's certificate to prove trust
        agent = await self.agent_service.get(message.recipient_id)
        if not agent:
            return self._create_response(
                message,
                MessageType.TRUST_FAILED,
                {"reason": "Agent not found"},
            )

        # Get active certificate
        certs = await self.certificate_service.list_for_agent(message.recipient_id)
        active_cert = next((c for c in certs if c.status == "active"), None)

        if not active_cert:
            return self._create_response(
                message,
                MessageType.TRUST_FAILED,
                {"reason": "No active certificate"},
            )

        # Check capabilities
        if challenge.required_capabilities:
            cert_caps = set(active_cert.capabilities or [])
            required = set(challenge.required_capabilities)
            missing = required - cert_caps
            if missing:
                return self._create_response(
                    message,
                    MessageType.TRUST_FAILED,
                    {"reason": "Missing capabilities", "missing": list(missing)},
                )

        # Check grade
        if challenge.minimum_grade:
            grade_order = {"A": 5, "B": 4, "C": 3, "D": 2, "F": 1}
            cert_grade = grade_order.get(active_cert.grade, 0)
            min_grade = grade_order.get(challenge.minimum_grade, 0)
            if cert_grade < min_grade:
                return self._create_response(
                    message,
                    MessageType.TRUST_FAILED,
                    {"reason": f"Certificate grade {active_cert.grade} below minimum {challenge.minimum_grade}"},
                )

        # Sign the nonce with the agent's private key
        from app.services.agent_keys import sign_nonce

        signature = await sign_nonce(message.recipient_id, challenge.nonce)

        proof = TrustProof(
            challenge_id=challenge.challenge_id,
            certificate_id=active_cert.id,
            nonce_signature=signature,
            capabilities=active_cert.capabilities or [],
            grade=active_cert.grade,
            valid_until=active_cert.valid_until,
        )

        return self._create_response(
            message,
            MessageType.TRUST_PROOF,
            {
                "challenge_id": str(proof.challenge_id),
                "certificate_id": str(proof.certificate_id),
                "nonce_signature": proof.nonce_signature,
                "capabilities": proof.capabilities,
                "grade": proof.grade,
                "valid_until": proof.valid_until.isoformat() if proof.valid_until else None,
            },
        )

    async def _handle_trust_proof(self, message: TACPMessage) -> Optional[TACPMessage]:
        """Handle a trust proof response."""
        try:
            proof = TrustProof.from_dict(message.payload)
        except Exception as e:
            return self._create_response(
                message,
                MessageType.TRUST_FAILED,
                {"reason": f"Invalid proof format: {e}"},
            )

        # Get the original challenge
        challenge = self._pending_challenges.pop(proof.challenge_id, None)
        if not challenge:
            return self._create_response(
                message,
                MessageType.TRUST_FAILED,
                {"reason": "Challenge not found or expired"},
            )

        # Verify the certificate exists and is valid
        cert = await self.certificate_service.get(proof.certificate_id)
        if not cert:
            return self._create_response(
                message,
                MessageType.TRUST_FAILED,
                {"reason": "Certificate not found"},
            )

        if cert.status != "active":
            return self._create_response(
                message,
                MessageType.TRUST_FAILED,
                {"reason": f"Certificate is {cert.status}"},
            )

        # Verify the signature
        from app.services.agent_keys import verify_signature

        is_valid = await verify_signature(
            agent_id=message.sender_id,
            message=challenge.nonce,
            signature=proof.nonce_signature,
        )

        if not is_valid:
            return self._create_response(
                message,
                MessageType.TRUST_FAILED,
                {"reason": "Invalid signature"},
            )

        # Verify capabilities
        if challenge.required_capabilities:
            missing = set(challenge.required_capabilities) - set(proof.capabilities)
            if missing:
                return self._create_response(
                    message,
                    MessageType.TRUST_FAILED,
                    {"reason": "Missing capabilities", "missing": list(missing)},
                )

        logger.info(
            "Trust verified",
            sender=str(message.sender_id),
            certificate_id=str(proof.certificate_id),
        )

        return self._create_response(
            message,
            MessageType.TRUST_VERIFIED,
            {
                "certificate_id": str(proof.certificate_id),
                "capabilities": proof.capabilities,
                "grade": proof.grade,
            },
        )

    async def _handle_capability_query(self, message: TACPMessage) -> Optional[TACPMessage]:
        """Handle a capability query."""
        requested_capabilities = message.payload.get("capabilities", [])
        include_scores = message.payload.get("include_scores", False)

        # Get the agent's certificate
        certs = await self.certificate_service.list_for_agent(message.recipient_id)
        active_cert = next((c for c in certs if c.status == "active"), None)

        if not active_cert:
            return self._create_response(
                message,
                MessageType.CAPABILITY_RESPONSE,
                {
                    "has_certificate": False,
                    "capabilities": [],
                    "message": "No active certificate",
                },
            )

        # Build capability response
        agent_capabilities = active_cert.capabilities or []

        if requested_capabilities:
            # Check specific capabilities
            capability_results = {
                cap: cap in agent_capabilities
                for cap in requested_capabilities
            }
        else:
            # Return all capabilities
            capability_results = {cap: True for cap in agent_capabilities}

        response_payload = {
            "has_certificate": True,
            "capabilities": agent_capabilities,
            "capability_results": capability_results,
            "grade": active_cert.grade,
            "valid_until": active_cert.valid_until.isoformat() if active_cert.valid_until else None,
        }

        if include_scores and active_cert.scores:
            response_payload["scores"] = active_cert.scores

        return self._create_response(
            message,
            MessageType.CAPABILITY_RESPONSE,
            response_payload,
        )

    async def _handle_task_request(self, message: TACPMessage) -> Optional[TACPMessage]:
        """Handle a task delegation request."""
        task_type = message.payload.get("task_type")
        description = message.payload.get("description")
        parameters = message.payload.get("parameters", {})
        timeout_seconds = message.payload.get("timeout_seconds", 300)

        # Validate request
        if not task_type or not description:
            return self._create_response(
                message,
                MessageType.TASK_REJECT,
                {"reason": "Missing required fields: task_type, description"},
            )

        # Check if we can handle this task type
        agent = await self.agent_service.get(message.recipient_id)
        if not agent:
            return self._create_response(
                message,
                MessageType.TASK_REJECT,
                {"reason": "Agent not found"},
            )

        # Check capabilities
        declared_caps = agent.declared_capabilities or []
        if task_type not in declared_caps and f"task:{task_type}" not in declared_caps:
            return self._create_response(
                message,
                MessageType.TASK_REJECT,
                {
                    "reason": f"Task type '{task_type}' not in agent capabilities",
                    "available_capabilities": declared_caps,
                },
            )

        # Accept the task
        task_id = str(uuid4())

        logger.info(
            "Task accepted",
            task_id=task_id,
            task_type=task_type,
            from_agent=str(message.sender_id),
        )

        # Increment task count in session
        await self.session_service.increment_task_count(message.session_id)

        return self._create_response(
            message,
            MessageType.TASK_ACCEPT,
            {
                "task_id": task_id,
                "task_type": task_type,
                "estimated_duration_seconds": timeout_seconds,
            },
        )

    async def _handle_task_progress(self, message: TACPMessage) -> Optional[TACPMessage]:
        """Handle a task progress update."""
        task_id = message.payload.get("task_id")
        progress_percent = message.payload.get("progress_percent", 0)
        status_message = message.payload.get("message", "")

        logger.debug(
            "Task progress",
            task_id=task_id,
            progress=progress_percent,
        )

        # Just acknowledge - forward to the original requester
        return None

    async def _handle_task_complete(self, message: TACPMessage) -> Optional[TACPMessage]:
        """Handle a task completion."""
        task_id = message.payload.get("task_id")
        result = message.payload.get("result")

        logger.info(
            "Task completed",
            task_id=task_id,
        )

        # Just acknowledge - result will be forwarded
        return None

    async def _handle_task_failed(self, message: TACPMessage) -> Optional[TACPMessage]:
        """Handle a task failure."""
        task_id = message.payload.get("task_id")
        error = message.payload.get("error")
        partial_result = message.payload.get("partial_result")

        logger.warning(
            "Task failed",
            task_id=task_id,
            error=error,
        )

        return None

    async def _handle_ping(self, message: TACPMessage) -> Optional[TACPMessage]:
        """Handle a ping message."""
        return self._create_response(
            message,
            MessageType.PONG,
            {"timestamp": datetime.now(timezone.utc).isoformat()},
        )

    async def _handle_session_end(self, message: TACPMessage) -> Optional[TACPMessage]:
        """Handle a session end request."""
        reason = message.payload.get("reason", "Session ended by peer")

        await self.session_service.end(message.session_id, reason)

        logger.info(
            "Session ended",
            session_id=str(message.session_id),
            reason=reason,
        )

        return None

    def _create_response(
        self,
        original: TACPMessage,
        message_type: MessageType,
        payload: dict[str, Any],
    ) -> TACPMessage:
        """Create a response message."""
        return TACPMessage(
            message_type=message_type,
            sender_id=original.recipient_id,
            recipient_id=original.sender_id,
            session_id=original.session_id,
            payload=payload,
            in_reply_to=original.message_id,
        )

    def _create_error_response(
        self,
        original: TACPMessage,
        error_message: str,
    ) -> TACPMessage:
        """Create an error response message."""
        return self._create_response(
            original,
            MessageType.ERROR,
            {"error": error_message},
        )
