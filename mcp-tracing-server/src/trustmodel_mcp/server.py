"""MCP server for universal LLM tracing."""

import asyncio
import os
from typing import Any, Dict, Sequence

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    CallToolResult,
    ListToolsResult,
)

from trustmodel_mcp.storage.sqlite import SQLiteStorage
from trustmodel_mcp.tools import trace_tools
from trustmodel_mcp.extractors.registry import get_registry


# Create MCP server
server = Server("trustmodel-tracing")

# Global storage instance
_storage: SQLiteStorage | None = None


async def get_storage() -> SQLiteStorage:
    """Get or create storage instance."""
    global _storage
    if _storage is None:
        db_path = os.environ.get("TRUSTMODEL_DB_PATH")
        _storage = SQLiteStorage(db_path)
        await _storage.initialize()
    return _storage


# Tool definitions
TOOLS = [
    Tool(
        name="trace_llm_call",
        description="Capture an LLM API call (request + response) for tracing. Supports Anthropic (Claude) and OpenAI (GPT) out of the box.",
        inputSchema={
            "type": "object",
            "properties": {
                "agent_id": {
                    "type": "string",
                    "description": "Agent identifier"
                },
                "provider": {
                    "type": "string",
                    "enum": ["anthropic", "openai"],
                    "description": "LLM provider"
                },
                "request": {
                    "type": "object",
                    "description": "The API request body"
                },
                "response": {
                    "type": "object",
                    "description": "The API response body"
                },
                "thread_id": {
                    "type": "string",
                    "description": "Optional conversation thread ID for multi-turn conversations"
                },
                "latency_ms": {
                    "type": "number",
                    "description": "Request latency in milliseconds"
                }
            },
            "required": ["agent_id", "provider", "request", "response"]
        }
    ),
    Tool(
        name="trace_tool_call",
        description="Capture a tool/function execution for tracing.",
        inputSchema={
            "type": "object",
            "properties": {
                "agent_id": {
                    "type": "string",
                    "description": "Agent identifier"
                },
                "tool_name": {
                    "type": "string",
                    "description": "Name of the tool"
                },
                "tool_input": {
                    "type": "object",
                    "description": "Tool input arguments"
                },
                "tool_output": {
                    "type": "string",
                    "description": "Tool output/result"
                },
                "thread_id": {
                    "type": "string",
                    "description": "Optional conversation thread ID"
                },
                "latency_ms": {
                    "type": "number",
                    "description": "Execution latency in milliseconds"
                },
                "success": {
                    "type": "boolean",
                    "description": "Whether the tool call succeeded",
                    "default": True
                }
            },
            "required": ["agent_id", "tool_name", "tool_input", "tool_output"]
        }
    ),
    Tool(
        name="start_trace",
        description="Start a new trace for a conversation. Returns trace_id and thread_id.",
        inputSchema={
            "type": "object",
            "properties": {
                "agent_id": {
                    "type": "string",
                    "description": "Agent identifier"
                },
                "thread_id": {
                    "type": "string",
                    "description": "Optional custom thread ID (auto-generated if omitted)"
                },
                "metadata": {
                    "type": "object",
                    "description": "Optional custom metadata"
                }
            },
            "required": ["agent_id"]
        }
    ),
    Tool(
        name="end_trace",
        description="End and finalize a trace.",
        inputSchema={
            "type": "object",
            "properties": {
                "trace_id": {
                    "type": "string",
                    "description": "Trace ID to end"
                },
                "status": {
                    "type": "string",
                    "enum": ["completed", "failed", "cancelled"],
                    "description": "Final status",
                    "default": "completed"
                },
                "error_message": {
                    "type": "string",
                    "description": "Optional error message for failed traces"
                }
            },
            "required": ["trace_id"]
        }
    ),
    Tool(
        name="get_traces",
        description="List traces with optional filters.",
        inputSchema={
            "type": "object",
            "properties": {
                "agent_id": {
                    "type": "string",
                    "description": "Filter by agent ID"
                },
                "limit": {
                    "type": "number",
                    "description": "Maximum number of traces to return",
                    "default": 20
                },
                "offset": {
                    "type": "number",
                    "description": "Number of traces to skip",
                    "default": 0
                },
                "status": {
                    "type": "string",
                    "enum": ["running", "completed", "failed"],
                    "description": "Filter by status"
                }
            }
        }
    ),
    Tool(
        name="get_trace_detail",
        description="Get complete trace details including all messages in LangSmith-compatible format.",
        inputSchema={
            "type": "object",
            "properties": {
                "trace_id": {
                    "type": "string",
                    "description": "Trace ID to retrieve"
                }
            },
            "required": ["trace_id"]
        }
    ),
]


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> Sequence[TextContent]:
    """Handle tool calls."""
    import json

    storage = await get_storage()
    result: Dict[str, Any] = {}

    try:
        if name == "trace_llm_call":
            result = await trace_tools.trace_llm_call(
                storage=storage,
                agent_id=arguments["agent_id"],
                provider=arguments["provider"],
                request=arguments["request"],
                response=arguments["response"],
                thread_id=arguments.get("thread_id"),
                latency_ms=arguments.get("latency_ms", 0),
            )

        elif name == "trace_tool_call":
            result = await trace_tools.trace_tool_call(
                storage=storage,
                agent_id=arguments["agent_id"],
                tool_name=arguments["tool_name"],
                tool_input=arguments["tool_input"],
                tool_output=arguments["tool_output"],
                thread_id=arguments.get("thread_id"),
                latency_ms=arguments.get("latency_ms", 0),
                success=arguments.get("success", True),
            )

        elif name == "start_trace":
            result = await trace_tools.start_trace(
                storage=storage,
                agent_id=arguments["agent_id"],
                thread_id=arguments.get("thread_id"),
                metadata=arguments.get("metadata"),
            )

        elif name == "end_trace":
            result = await trace_tools.end_trace(
                storage=storage,
                trace_id=arguments["trace_id"],
                status=arguments.get("status", "completed"),
                error_message=arguments.get("error_message"),
            )

        elif name == "get_traces":
            result = await trace_tools.get_traces(
                storage=storage,
                agent_id=arguments.get("agent_id"),
                limit=arguments.get("limit", 20),
                offset=arguments.get("offset", 0),
                status=arguments.get("status"),
            )

        elif name == "get_trace_detail":
            result = await trace_tools.get_trace_detail(
                storage=storage,
                trace_id=arguments["trace_id"],
            )

        else:
            result = {"error": f"Unknown tool: {name}"}

    except Exception as e:
        result = {"error": str(e)}

    return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]


def main():
    """Main entry point."""
    async def run():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )

    asyncio.run(run())


if __name__ == "__main__":
    main()
