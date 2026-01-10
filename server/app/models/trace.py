"""Trace and Span models for agent activity tracking."""

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, List, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.agent import Agent


class SpanType(str, Enum):
    """Types of spans in a trace."""

    LLM_CALL = "llm_call"
    TOOL_CALL = "tool_call"
    DECISION = "decision"
    FILE_OPERATION = "file_operation"
    API_CALL = "api_call"
    CUSTOM = "custom"


class SpanStatus(str, Enum):
    """Status of a span."""

    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"


class Trace(Base, UUIDMixin, TimestampMixin):
    """A trace representing a complete agent session or task."""

    __tablename__ = "traces"

    # Agent relationship
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent: Mapped["Agent"] = relationship("Agent", back_populates="traces")

    # Session info
    session_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="External session identifier",
    )
    task_description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Human-readable task description",
    )

    # Timing
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Aggregated metrics
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_cost_usd: Mapped[Optional[float]] = mapped_column(nullable=True)
    tool_call_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Metadata (using trace_metadata as 'metadata' is reserved by SQLAlchemy)
    trace_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )

    # Relationships
    spans: Mapped[List["Span"]] = relationship(
        "Span",
        back_populates="trace",
        cascade="all, delete-orphan",
        order_by="Span.started_at",
    )

    @property
    def duration_ms(self) -> Optional[int]:
        """Calculate trace duration in milliseconds."""
        if self.ended_at and self.started_at:
            delta = self.ended_at - self.started_at
            return int(delta.total_seconds() * 1000)
        return None


class Span(Base, UUIDMixin):
    """A span representing a single operation within a trace."""

    __tablename__ = "spans"

    # Trace relationship
    trace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("traces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    trace: Mapped["Trace"] = relationship("Trace", back_populates="spans")

    # Parent span (for nested operations)
    parent_span_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("spans.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Span info
    span_type: Mapped[SpanType] = mapped_column(
        String(50),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Timing
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Status
    status: Mapped[SpanStatus] = mapped_column(
        String(20),
        default=SpanStatus.OK,
        nullable=False,
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Attributes (specific to span type)
    attributes: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        comment="Span-specific attributes (e.g., model, tokens for LLM calls)",
    )

    @property
    def duration_ms(self) -> Optional[int]:
        """Calculate span duration in milliseconds."""
        if self.ended_at and self.started_at:
            delta = self.ended_at - self.started_at
            return int(delta.total_seconds() * 1000)
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# Span Attribute Types (for documentation/validation)
# ═══════════════════════════════════════════════════════════════════════════════

# LLM Call Attributes:
# {
#     "model": str,
#     "provider": str,
#     "prompt_tokens": int,
#     "completion_tokens": int,
#     "temperature": float,
#     "prompt_preview": str,  # First 500 chars
#     "completion_preview": str,  # First 500 chars
# }

# Tool Call Attributes:
# {
#     "tool_name": str,
#     "input": str | dict,
#     "output": str | dict,
#     "success": bool,
# }

# Decision Attributes:
# {
#     "question": str,
#     "reasoning": str,
#     "decision": str,
#     "confidence": float,
#     "alternatives_considered": int,
# }

# File Operation Attributes:
# {
#     "action": str,  # read, write, edit, delete
#     "path": str,
#     "changes_summary": str,
# }
