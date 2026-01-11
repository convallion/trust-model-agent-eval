"""Chat endpoint for interacting with agents."""

import asyncio
import time
import uuid as uuid_lib
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import settings
from app.core.database import get_db
from app.models.trace import Trace, Span, SpanType
from app.models.user import User
from app.services.agent_service import AgentService

router = APIRouter()


class ChatMessage(BaseModel):
    role: str  # "user", "assistant", "system"
    content: str


class ChatRequest(BaseModel):
    agent_id: str
    messages: List[ChatMessage]
    max_tokens: int = 1024


class ToolCall(BaseModel):
    name: str
    success: bool
    duration_ms: int


class ChatResponse(BaseModel):
    id: str
    agent_id: str
    content: str
    role: str = "assistant"
    trace_id: str
    latency_ms: int
    status: str  # "success" or "error"
    tool_calls: List[ToolCall] = []
    model: Optional[str] = None
    tokens_used: Optional[int] = None


async def call_anthropic_api(messages: List[ChatMessage], max_tokens: int) -> dict:
    """Call Anthropic API directly."""
    import anthropic

    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Anthropic API key not configured. Set ANTHROPIC_API_KEY environment variable.",
        )

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    # Convert messages to Anthropic format
    anthropic_messages = []
    system_message = None

    for msg in messages:
        if msg.role == "system":
            system_message = msg.content
        else:
            anthropic_messages.append({
                "role": msg.role,
                "content": msg.content,
            })

    start_time = time.time()

    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=max_tokens,
        system=system_message or "You are a helpful AI assistant.",
        messages=anthropic_messages,
    )

    latency_ms = int((time.time() - start_time) * 1000)

    return {
        "content": response.content[0].text,
        "model": response.model,
        "tokens_used": response.usage.input_tokens + response.usage.output_tokens,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "latency_ms": latency_ms,
        "tool_calls": [],  # Claude API doesn't expose tool calls in this format
    }


async def call_claude_code_proxy(messages: List[ChatMessage]) -> dict:
    """
    Proxy to local Claude Code.
    This creates a subprocess that interacts with Claude Code CLI.
    """
    import subprocess
    import json

    # Get the last user message
    user_message = None
    for msg in reversed(messages):
        if msg.role == "user":
            user_message = msg.content
            break

    if not user_message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No user message found",
        )

    start_time = time.time()

    try:
        # Use Claude Code CLI in non-interactive mode
        # This requires claude-code to be installed and in PATH
        result = subprocess.run(
            ["claude", "-p", user_message, "--output-format", "json"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd="/tmp",
        )

        latency_ms = int((time.time() - start_time) * 1000)

        if result.returncode != 0:
            # Try to parse error or return stderr
            return {
                "content": f"Claude Code returned an error: {result.stderr or 'Unknown error'}",
                "model": "claude-code-local",
                "tokens_used": None,
                "latency_ms": latency_ms,
                "tool_calls": [],
                "status": "error",
            }

        # Parse the JSON output if available
        try:
            output = json.loads(result.stdout)
            content = output.get("result", result.stdout)
            tool_calls = []

            # Extract tool calls if present
            if "tool_uses" in output:
                for tool in output["tool_uses"]:
                    tool_calls.append({
                        "name": tool.get("name", "unknown"),
                        "success": tool.get("success", True),
                        "duration_ms": tool.get("duration_ms", 0),
                    })
        except json.JSONDecodeError:
            content = result.stdout
            tool_calls = []

        return {
            "content": content,
            "model": "claude-code-local",
            "tokens_used": None,
            "latency_ms": latency_ms,
            "tool_calls": tool_calls,
            "status": "success",
        }

    except subprocess.TimeoutExpired:
        latency_ms = int((time.time() - start_time) * 1000)
        return {
            "content": "Claude Code timed out after 60 seconds",
            "model": "claude-code-local",
            "tokens_used": None,
            "latency_ms": latency_ms,
            "tool_calls": [],
            "status": "error",
        }
    except FileNotFoundError:
        return {
            "content": "Claude Code CLI not found. Please install it with: npm install -g @anthropic-ai/claude-code",
            "model": "claude-code-local",
            "tokens_used": None,
            "latency_ms": 0,
            "tool_calls": [],
            "status": "error",
        }


async def record_trace(
    db: AsyncSession,
    agent_id: UUID,
    messages: List[ChatMessage],
    result: dict,
    status_str: str,
) -> Trace:
    """Record a trace and spans for the chat interaction."""
    now = datetime.now(timezone.utc)
    latency_ms = result.get("latency_ms", 0)

    # Create trace
    trace = Trace(
        id=uuid_lib.uuid4(),
        agent_id=agent_id,
        started_at=now - timedelta(milliseconds=latency_ms),
        ended_at=now,
        trace_metadata={"source": "chat_endpoint"},
    )
    db.add(trace)
    await db.flush()  # Get trace ID

    # Create LLM span
    llm_span = Span(
        id=uuid_lib.uuid4(),
        trace_id=trace.id,
        parent_span_id=None,
        span_type=SpanType.LLM,
        name="llm_call",
        started_at=trace.started_at,
        ended_at=trace.ended_at,
        status="success" if status_str == "success" else "error",
        attributes={
            "model": result.get("model"),
            "input_tokens": result.get("input_tokens"),
            "output_tokens": result.get("output_tokens"),
            "total_tokens": result.get("tokens_used"),
            "latency_ms": latency_ms,
            "messages_count": len(messages),
            "user_message": messages[-1].content if messages else None,
            "response_preview": result.get("content", "")[:200] if result.get("content") else None,
        },
    )
    db.add(llm_span)

    # Create tool spans if any
    for i, tool_call in enumerate(result.get("tool_calls", [])):
        tool_name = tool_call.get("name", "unknown") if isinstance(tool_call, dict) else tool_call.name
        tool_success = tool_call.get("success", True) if isinstance(tool_call, dict) else tool_call.success
        tool_duration = tool_call.get("duration_ms", 0) if isinstance(tool_call, dict) else tool_call.duration_ms

        tool_span = Span(
            id=uuid_lib.uuid4(),
            trace_id=trace.id,
            parent_span_id=llm_span.id,
            span_type=SpanType.TOOL,
            name=tool_name,
            started_at=trace.started_at,
            ended_at=trace.started_at + timedelta(milliseconds=tool_duration),
            status="success" if tool_success else "error",
            attributes={
                "tool_name": tool_name,
                "duration_ms": tool_duration,
            },
        )
        db.add(tool_span)

    await db.commit()
    return trace


@router.post("", response_model=ChatResponse)
async def chat_with_agent(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    """Send a message to an agent and get a response."""

    # Verify agent access
    agent_service = AgentService(db)
    agent = await agent_service.get(UUID(request.agent_id))

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    if agent.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to use this agent",
        )

    # Route based on agent type/framework
    try:
        if agent.framework == "anthropic-api":
            # Direct Anthropic API call
            result = await call_anthropic_api(request.messages, request.max_tokens)
            status_str = "success"
        elif agent.framework == "claude-code":
            # Proxy to local Claude Code
            result = await call_claude_code_proxy(request.messages)
            status_str = result.get("status", "success")
        else:
            # Default to Anthropic API
            result = await call_anthropic_api(request.messages, request.max_tokens)
            status_str = "success"

    except HTTPException:
        raise
    except Exception as e:
        # Record error trace
        error_result = {
            "content": f"Error: {str(e)}",
            "model": None,
            "tokens_used": None,
            "latency_ms": 0,
            "tool_calls": [],
        }
        try:
            trace = await record_trace(db, agent.id, request.messages, error_result, "error")
            trace_id = str(trace.id)
        except:
            trace_id = f"error-{uuid_lib.uuid4().hex[:12]}"

        return ChatResponse(
            id=f"msg-{uuid_lib.uuid4().hex[:8]}",
            agent_id=request.agent_id,
            content=f"Error: {str(e)}",
            trace_id=trace_id,
            latency_ms=0,
            status="error",
            tool_calls=[],
        )

    # Record the trace
    try:
        trace = await record_trace(db, agent.id, request.messages, result, status_str)
        trace_id = str(trace.id)
    except Exception as e:
        # If trace recording fails, still return the response
        trace_id = f"trace-{uuid_lib.uuid4().hex[:12]}"

    return ChatResponse(
        id=f"msg-{uuid_lib.uuid4().hex[:8]}",
        agent_id=request.agent_id,
        content=result["content"],
        trace_id=trace_id,
        latency_ms=result["latency_ms"],
        status=status_str,
        tool_calls=[ToolCall(**tc) if isinstance(tc, dict) else tc for tc in result.get("tool_calls", [])],
        model=result.get("model"),
        tokens_used=result.get("tokens_used"),
    )
