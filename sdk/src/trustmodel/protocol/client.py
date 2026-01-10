"""TACP Client for establishing agent connections."""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from trustmodel.api.client import TrustModelClient, get_client
from trustmodel.core.config import get_config
from trustmodel.core.exceptions import ProtocolError, TrustVerificationError
from trustmodel.core.logging import get_logger
from trustmodel.protocol.session import TACPSession

logger = get_logger(__name__)


class TACPClient:
    """Client for establishing TACP connections."""

    def __init__(self, client: Optional[TrustModelClient] = None) -> None:
        self._client = client or get_client()

    async def connect(
        self,
        to_agent: str | UUID,
        purpose: str,
        needed_capabilities: Optional[list[str]] = None,
        constraints: Optional[dict[str, Any]] = None,
        verify_trust: bool = True,
        minimum_grade: Optional[str] = None,
    ) -> TACPSession:
        """
        Connect to another agent.

        Args:
            to_agent: Agent name or ID to connect to
            purpose: Purpose of the connection
            needed_capabilities: Required capabilities for the remote agent
            constraints: Constraints for the session
            verify_trust: Whether to verify trust before proceeding
            minimum_grade: Minimum certificate grade required

        Returns:
            TACPSession for communication

        Raises:
            TrustVerificationError: If trust verification fails
        """
        config = get_config()

        # Resolve agent IDs
        local_agent_id = UUID(config.agent_id) if config.agent_id else None
        if not local_agent_id:
            raise ProtocolError("Local agent ID not configured")

        # Resolve remote agent
        if isinstance(to_agent, str):
            try:
                remote_agent_id = UUID(to_agent)
                # Get agent name
                agent_info = await self._client.get_agent(remote_agent_id)
                remote_agent_name = agent_info["name"]
            except ValueError:
                # Look up by name
                agents = await self._client.list_agents()
                remote_agent_id = None
                remote_agent_name = to_agent
                for a in agents.get("items", []):
                    if a["name"] == to_agent:
                        remote_agent_id = UUID(a["id"])
                        break
                if not remote_agent_id:
                    raise ProtocolError(f"Agent not found: {to_agent}")
        else:
            remote_agent_id = to_agent
            agent_info = await self._client.get_agent(remote_agent_id)
            remote_agent_name = agent_info["name"]

        # Create session on server
        session_data = await self._client.create_session({
            "initiator_agent_id": str(local_agent_id),
            "responder_agent_id": str(remote_agent_id),
            "purpose": purpose,
            "needed_capabilities": needed_capabilities or [],
            "constraints": constraints or {},
        })

        session_id = UUID(session_data["id"])

        # Build WebSocket URL
        ws_url = config.server_url.replace("http", "ws")
        ws_url = f"{ws_url}/v1/sessions/{session_id}/ws"

        # Create session object
        session = TACPSession(
            session_id=session_id,
            local_agent_id=local_agent_id,
            remote_agent_id=remote_agent_id,
            remote_agent_name=remote_agent_name,
            purpose=purpose,
            constraints=constraints or {},
            ws_url=ws_url,
        )

        # Connect WebSocket
        await session.connect()

        # Verify trust if requested
        if verify_trust:
            try:
                await session.verify_trust(
                    required_capabilities=needed_capabilities,
                    minimum_grade=minimum_grade,
                )
            except TrustVerificationError:
                await session.end()
                raise

        logger.info(
            "Connected to agent",
            session_id=str(session_id),
            remote_agent=remote_agent_name,
            trust_verified=verify_trust,
        )

        return session

    async def accept(self, session_id: UUID) -> TACPSession:
        """
        Accept an incoming session request.

        Args:
            session_id: The session to accept

        Returns:
            TACPSession for communication
        """
        config = get_config()
        local_agent_id = UUID(config.agent_id) if config.agent_id else None

        # Accept on server
        session_data = await self._client.accept_session(session_id)

        # Build WebSocket URL
        ws_url = config.server_url.replace("http", "ws")
        ws_url = f"{ws_url}/v1/sessions/{session_id}/ws"

        # Create session object
        session = TACPSession(
            session_id=session_id,
            local_agent_id=local_agent_id,
            remote_agent_id=UUID(session_data["initiator_agent_id"]),
            remote_agent_name=session_data["initiator_agent_name"],
            purpose=session_data.get("purpose", ""),
            constraints=session_data.get("constraints", {}),
            ws_url=ws_url,
        )

        await session.connect()

        return session

    async def list_pending(self, agent_id: Optional[UUID] = None) -> list[dict[str, Any]]:
        """List pending session requests for an agent."""
        config = get_config()
        agent_id = agent_id or (UUID(config.agent_id) if config.agent_id else None)

        if not agent_id:
            raise ProtocolError("Agent ID not configured")

        response = await self._client.get(
            "/v1/sessions",
            params={
                "agent_id": str(agent_id),
                "status": "pending",
            },
        )

        return response.get("items", [])


async def connect(
    to_agent: str | UUID,
    purpose: str,
    needed_capabilities: Optional[list[str]] = None,
    constraints: Optional[dict[str, Any]] = None,
    verify_trust: bool = True,
    minimum_grade: Optional[str] = None,
) -> TACPSession:
    """
    Connect to another agent.

    This is the main entry point for agent-to-agent communication.

    Args:
        to_agent: Agent name or ID to connect to (e.g., "research-lab/paper-analyzer")
        purpose: Purpose of the connection
        needed_capabilities: Required capabilities for the remote agent
        constraints: Constraints for the session
        verify_trust: Whether to verify trust before proceeding (default: True)
        minimum_grade: Minimum certificate grade required (e.g., "B")

    Returns:
        TACPSession for communication

    Example:
        from trustmodel import connect

        async with await connect(
            to_agent="research-lab/paper-analyzer",
            purpose="Research security best practices",
            needed_capabilities=["research"],
        ) as session:
            result = await session.request_task(
                task_type="research",
                description="JWT auth best practices",
            )
            print(result.result)
    """
    client = TACPClient()
    return await client.connect(
        to_agent=to_agent,
        purpose=purpose,
        needed_capabilities=needed_capabilities,
        constraints=constraints,
        verify_trust=verify_trust,
        minimum_grade=minimum_grade,
    )
