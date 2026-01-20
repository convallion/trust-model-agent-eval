"""Data models for traces - LangSmith compatible format."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from enum import Enum
import uuid


class TraceStatus(str, Enum):
    """Status of a trace."""
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class MessageType(str, Enum):
    """Type of message in a trace."""
    HUMAN = "human"
    AI = "ai"
    TOOL = "tool"
    SYSTEM = "system"


@dataclass
class ToolCall:
    """A tool call made by the AI."""
    id: str
    name: str
    args: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "args": self.args,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolCall":
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            args=data.get("args", {}),
        )


@dataclass
class UsageMetadata:
    """Token usage information."""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UsageMetadata":
        return cls(
            input_tokens=data.get("input_tokens", 0),
            output_tokens=data.get("output_tokens", 0),
            total_tokens=data.get("total_tokens", 0),
        )


@dataclass
class ResponseMetadata:
    """Response metadata from the LLM."""
    model_name: Optional[str] = None
    finish_reason: Optional[str] = None
    latency_ms: Optional[float] = None
    provider: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {}
        if self.model_name:
            result["model_name"] = self.model_name
        if self.finish_reason:
            result["finish_reason"] = self.finish_reason
        if self.latency_ms is not None:
            result["latency_ms"] = self.latency_ms
        if self.provider:
            result["provider"] = self.provider
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResponseMetadata":
        return cls(
            model_name=data.get("model_name"),
            finish_reason=data.get("finish_reason"),
            latency_ms=data.get("latency_ms"),
            provider=data.get("provider"),
        )


@dataclass
class Message:
    """A message in the conversation - LangSmith compatible format."""
    type: MessageType
    content: str = ""
    name: Optional[str] = None  # For tool messages
    tool_calls: Optional[List[ToolCall]] = None
    tool_call_id: Optional[str] = None  # For tool response messages
    usage_metadata: Optional[UsageMetadata] = None
    response_metadata: Optional[ResponseMetadata] = None
    timestamp: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to LangSmith-compatible dict format."""
        result: Dict[str, Any] = {
            "type": self.type.value if isinstance(self.type, MessageType) else self.type,
            "content": self.content,
        }

        if self.name:
            result["name"] = self.name

        if self.tool_calls:
            result["tool_calls"] = [tc.to_dict() for tc in self.tool_calls]

        if self.tool_call_id:
            result["tool_call_id"] = self.tool_call_id

        if self.usage_metadata:
            result["usage_metadata"] = self.usage_metadata.to_dict()

        if self.response_metadata:
            result["response_metadata"] = self.response_metadata.to_dict()

        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        msg_type = data.get("type", "human")
        if isinstance(msg_type, str):
            msg_type = MessageType(msg_type)

        tool_calls = None
        if data.get("tool_calls"):
            tool_calls = [ToolCall.from_dict(tc) for tc in data["tool_calls"]]

        usage = None
        if data.get("usage_metadata"):
            usage = UsageMetadata.from_dict(data["usage_metadata"])

        response = None
        if data.get("response_metadata"):
            response = ResponseMetadata.from_dict(data["response_metadata"])

        return cls(
            type=msg_type,
            content=data.get("content", ""),
            name=data.get("name"),
            tool_calls=tool_calls,
            tool_call_id=data.get("tool_call_id"),
            usage_metadata=usage,
            response_metadata=response,
        )


@dataclass
class Trace:
    """A complete trace - LangSmith compatible format."""
    id: str
    thread_id: str
    agent_id: str
    created_at: datetime
    updated_at: datetime
    status: TraceStatus
    messages: List[Message] = field(default_factory=list)

    # Aggregated stats
    total_tokens: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    tool_call_count: int = 0
    latency_ms: float = 0

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    provider: Optional[str] = None
    model: Optional[str] = None

    @classmethod
    def create(
        cls,
        agent_id: str,
        thread_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "Trace":
        """Create a new trace."""
        now = datetime.now(timezone.utc)
        return cls(
            id=str(uuid.uuid4()),
            thread_id=thread_id or str(uuid.uuid4()),
            agent_id=agent_id,
            created_at=now,
            updated_at=now,
            status=TraceStatus.RUNNING,
            metadata=metadata or {},
        )

    def add_message(self, message: Message) -> None:
        """Add a message and update stats."""
        self.messages.append(message)
        self.updated_at = datetime.now(timezone.utc)

        # Update token counts
        if message.usage_metadata:
            self.total_input_tokens += message.usage_metadata.input_tokens
            self.total_output_tokens += message.usage_metadata.output_tokens
            self.total_tokens += message.usage_metadata.total_tokens

        # Update tool call count
        if message.tool_calls:
            self.tool_call_count += len(message.tool_calls)

        # Update latency
        if message.response_metadata and message.response_metadata.latency_ms:
            self.latency_ms += message.response_metadata.latency_ms

        # Update model/provider
        if message.response_metadata:
            if message.response_metadata.model_name:
                self.model = message.response_metadata.model_name
            if message.response_metadata.provider:
                self.provider = message.response_metadata.provider

    def complete(self) -> None:
        """Mark trace as completed."""
        self.status = TraceStatus.COMPLETED
        self.updated_at = datetime.now(timezone.utc)

    def fail(self, error: Optional[str] = None) -> None:
        """Mark trace as failed."""
        self.status = TraceStatus.FAILED
        self.updated_at = datetime.now(timezone.utc)
        if error:
            self.metadata["error"] = error

    def to_dict(self) -> Dict[str, Any]:
        """Convert to LangSmith-compatible dict format."""
        return {
            "id": self.id,
            "thread_id": self.thread_id,
            "agent_id": self.agent_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "status": self.status.value,
            "messages": [m.to_dict() for m in self.messages],
            "total_tokens": self.total_tokens,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "tool_call_count": self.tool_call_count,
            "latency_ms": self.latency_ms,
            "metadata": self.metadata,
            "provider": self.provider,
            "model": self.model,
        }

    def to_summary(self) -> Dict[str, Any]:
        """Convert to summary format (without full messages)."""
        last_message = None
        if self.messages:
            last_msg = self.messages[-1]
            content = last_msg.content[:200] if last_msg.content else ""
            last_message = content

        return {
            "id": self.id,
            "thread_id": self.thread_id,
            "agent_id": self.agent_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "status": self.status.value,
            "message_count": len(self.messages),
            "total_tokens": self.total_tokens,
            "tool_call_count": self.tool_call_count,
            "latency_ms": self.latency_ms,
            "provider": self.provider,
            "model": self.model,
            "last_message": last_message,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Trace":
        """Create trace from dict."""
        messages = [Message.from_dict(m) for m in data.get("messages", [])]

        status = data.get("status", "running")
        if isinstance(status, str):
            status = TraceStatus(status)

        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))

        updated_at = data.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))

        return cls(
            id=data["id"],
            thread_id=data["thread_id"],
            agent_id=data["agent_id"],
            created_at=created_at,
            updated_at=updated_at,
            status=status,
            messages=messages,
            total_tokens=data.get("total_tokens", 0),
            total_input_tokens=data.get("total_input_tokens", 0),
            total_output_tokens=data.get("total_output_tokens", 0),
            tool_call_count=data.get("tool_call_count", 0),
            latency_ms=data.get("latency_ms", 0),
            metadata=data.get("metadata", {}),
            provider=data.get("provider"),
            model=data.get("model"),
        )
