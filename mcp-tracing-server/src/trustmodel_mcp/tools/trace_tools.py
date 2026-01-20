"""MCP tool implementations for tracing."""

from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from trustmodel_mcp.models import (
    Trace,
    Message,
    MessageType,
    ToolCall,
    TraceStatus,
)
from trustmodel_mcp.extractors.registry import get_registry
from trustmodel_mcp.storage.base import StorageBackend


async def trace_llm_call(
    storage: StorageBackend,
    agent_id: str,
    provider: str,
    request: Dict[str, Any],
    response: Dict[str, Any],
    thread_id: Optional[str] = None,
    latency_ms: float = 0,
) -> Dict[str, Any]:
    """Capture an LLM API call for tracing.

    Args:
        storage: Storage backend
        agent_id: Agent identifier
        provider: LLM provider (anthropic, openai)
        request: The API request body
        response: The API response body
        thread_id: Optional conversation thread ID
        latency_ms: Request latency in milliseconds

    Returns:
        Dict with trace_id, thread_id, message_count, total_tokens
    """
    registry = get_registry()
    extractor = registry.get(provider)

    if not extractor:
        # Fallback: store raw request/response
        messages = _create_generic_messages(request, response, provider, latency_ms)
    else:
        messages = extractor.extract_messages(request, response, latency_ms)

    # Get or create trace for this thread
    trace = None
    if thread_id:
        trace = await storage.get_trace_by_thread(thread_id)

    if not trace:
        trace = Trace.create(
            agent_id=agent_id,
            thread_id=thread_id,
            metadata={"provider": provider},
        )

    # Add messages to trace
    for msg in messages:
        trace.add_message(msg)

    # Auto-complete trace (single request = complete)
    trace.complete()

    # Save
    await storage.save_trace(trace)

    return {
        "trace_id": trace.id,
        "thread_id": trace.thread_id,
        "message_count": len(trace.messages),
        "total_tokens": trace.total_tokens,
    }


async def trace_tool_call(
    storage: StorageBackend,
    agent_id: str,
    tool_name: str,
    tool_input: Dict[str, Any],
    tool_output: str,
    thread_id: Optional[str] = None,
    latency_ms: float = 0,
    success: bool = True,
) -> Dict[str, Any]:
    """Capture a tool execution for tracing.

    Args:
        storage: Storage backend
        agent_id: Agent identifier
        tool_name: Name of the tool
        tool_input: Tool input arguments
        tool_output: Tool output/result
        thread_id: Optional conversation thread ID
        latency_ms: Execution latency in milliseconds
        success: Whether the tool call succeeded

    Returns:
        Dict with trace_id, thread_id
    """
    # Get or create trace
    trace = None
    if thread_id:
        trace = await storage.get_trace_by_thread(thread_id)

    if not trace:
        trace = Trace.create(agent_id=agent_id, thread_id=thread_id)

    # Create tool message
    message = Message(
        type=MessageType.TOOL,
        content=tool_output,
        name=tool_name,
        timestamp=datetime.now(timezone.utc),
    )

    trace.add_message(message)
    trace.metadata["last_tool_call"] = {
        "name": tool_name,
        "success": success,
        "latency_ms": latency_ms,
    }

    await storage.save_trace(trace)

    return {
        "trace_id": trace.id,
        "thread_id": trace.thread_id,
    }


async def start_trace(
    storage: StorageBackend,
    agent_id: str,
    thread_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Start a new trace for a conversation.

    Args:
        storage: Storage backend
        agent_id: Agent identifier
        thread_id: Optional custom thread ID
        metadata: Optional custom metadata

    Returns:
        Dict with trace_id, thread_id
    """
    trace = Trace.create(
        agent_id=agent_id,
        thread_id=thread_id,
        metadata=metadata,
    )

    await storage.save_trace(trace)

    return {
        "trace_id": trace.id,
        "thread_id": trace.thread_id,
    }


async def end_trace(
    storage: StorageBackend,
    trace_id: str,
    status: str = "completed",
    error_message: Optional[str] = None,
) -> Dict[str, Any]:
    """End and finalize a trace.

    Args:
        storage: Storage backend
        trace_id: Trace ID to end
        status: Final status (completed, failed, cancelled)
        error_message: Optional error message for failed traces

    Returns:
        Dict with success status
    """
    trace = await storage.get_trace(trace_id)

    if not trace:
        return {"success": False, "error": "Trace not found"}

    if status == "failed":
        trace.fail(error_message)
    else:
        trace.status = TraceStatus(status) if status in ["completed", "cancelled"] else TraceStatus.COMPLETED
        trace.updated_at = datetime.now(timezone.utc)

    await storage.save_trace(trace)

    return {"success": True, "trace_id": trace_id, "status": trace.status.value}


async def get_traces(
    storage: StorageBackend,
    agent_id: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    status: Optional[str] = None,
) -> Dict[str, Any]:
    """List traces with optional filters.

    Args:
        storage: Storage backend
        agent_id: Filter by agent ID
        limit: Maximum number of traces to return
        offset: Number of traces to skip
        status: Filter by status

    Returns:
        Dict with traces list and total count
    """
    traces = await storage.list_traces(
        agent_id=agent_id,
        limit=limit,
        offset=offset,
        status=status,
    )

    total = await storage.count_traces(agent_id=agent_id, status=status)

    return {
        "traces": [t.to_summary() for t in traces],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


async def get_trace_detail(
    storage: StorageBackend,
    trace_id: str,
) -> Dict[str, Any]:
    """Get complete trace details including all messages.

    Args:
        storage: Storage backend
        trace_id: Trace ID to retrieve

    Returns:
        Full trace object or error
    """
    trace = await storage.get_trace(trace_id)

    if not trace:
        return {"success": False, "error": "Trace not found"}

    return {
        "success": True,
        **trace.to_dict(),
    }


def _create_generic_messages(
    request: Dict[str, Any],
    response: Dict[str, Any],
    provider: str,
    latency_ms: float,
) -> List[Message]:
    """Create generic messages when no extractor is available."""
    from trustmodel_mcp.models import ResponseMetadata

    messages = []

    # Try to extract some basic info
    model = response.get("model", request.get("model", "unknown"))

    # Create a single AI message with the response
    messages.append(
        Message(
            type=MessageType.AI,
            content=str(response.get("content", response)),
            response_metadata=ResponseMetadata(
                model_name=model,
                provider=provider,
                latency_ms=latency_ms,
            ),
        )
    )

    return messages
