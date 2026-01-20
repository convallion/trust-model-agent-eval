"""Unified trace ingestion schemas for any LLM provider."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ToolCallIngest(BaseModel):
    """Tool call information."""

    id: str
    name: str
    args: Dict[str, Any] = Field(default_factory=dict)


class UsageMetadata(BaseModel):
    """Token usage information."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class ResponseMetadata(BaseModel):
    """Response metadata from LLM."""

    model_name: Optional[str] = None
    finish_reason: Optional[str] = None
    latency_ms: Optional[float] = None
    provider: Optional[str] = None  # "anthropic", "openai", etc.


class MessageIngest(BaseModel):
    """A single message in the conversation."""

    type: str  # "human", "ai", "tool", "system"
    content: str = ""
    name: Optional[str] = None  # For tool messages, the tool name
    tool_calls: Optional[List[ToolCallIngest]] = None
    tool_call_id: Optional[str] = None  # For tool response messages
    usage_metadata: Optional[UsageMetadata] = None
    response_metadata: Optional[ResponseMetadata] = None
    timestamp: Optional[datetime] = None


class TraceIngestRequest(BaseModel):
    """Request to ingest a trace from any provider."""

    agent_id: UUID
    thread_id: Optional[str] = None  # For conversation continuity
    session_id: Optional[str] = None  # Alternative to thread_id
    messages: List[MessageIngest]
    metadata: Optional[Dict[str, Any]] = None

    # Optional trace-level info
    status: str = "completed"  # "running", "completed", "failed"
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None


class TraceIngestResponse(BaseModel):
    """Response after ingesting a trace."""

    success: bool
    trace_id: UUID
    thread_id: str
    message_count: int
    total_tokens: int


# Anthropic-specific request/response parsing
class AnthropicContentBlock(BaseModel):
    """Anthropic content block."""

    type: str  # "text", "tool_use", "tool_result"
    text: Optional[str] = None
    id: Optional[str] = None  # For tool_use
    name: Optional[str] = None  # For tool_use
    input: Optional[Dict[str, Any]] = None  # For tool_use
    tool_use_id: Optional[str] = None  # For tool_result
    content: Optional[str] = None  # For tool_result


class AnthropicMessage(BaseModel):
    """Anthropic message format."""

    role: str  # "user", "assistant"
    content: Any  # str or List[AnthropicContentBlock]


class AnthropicRequest(BaseModel):
    """Anthropic API request body."""

    model: str
    messages: List[AnthropicMessage]
    max_tokens: int = 1024
    system: Optional[str] = None
    tools: Optional[List[Dict[str, Any]]] = None
    temperature: Optional[float] = None


class AnthropicUsage(BaseModel):
    """Anthropic usage info."""

    input_tokens: int
    output_tokens: int


class AnthropicResponse(BaseModel):
    """Anthropic API response body."""

    id: str
    type: str
    role: str
    content: List[AnthropicContentBlock]
    model: str
    stop_reason: Optional[str] = None
    usage: AnthropicUsage


# OpenAI-specific request/response parsing
class OpenAIMessage(BaseModel):
    """OpenAI message format."""

    role: str  # "user", "assistant", "system", "tool"
    content: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None


class OpenAIRequest(BaseModel):
    """OpenAI API request body."""

    model: str
    messages: List[OpenAIMessage]
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    tools: Optional[List[Dict[str, Any]]] = None


class OpenAIChoice(BaseModel):
    """OpenAI response choice."""

    index: int
    message: OpenAIMessage
    finish_reason: Optional[str] = None


class OpenAIUsage(BaseModel):
    """OpenAI usage info."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class OpenAIResponse(BaseModel):
    """OpenAI API response body."""

    id: str
    object: str
    created: int
    model: str
    choices: List[OpenAIChoice]
    usage: OpenAIUsage
