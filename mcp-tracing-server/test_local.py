#!/usr/bin/env python3
"""Quick local test for the MCP tracing server components."""

import sys
import asyncio
sys.path.insert(0, "src")

from trustmodel_mcp.models import Trace, Message, MessageType, ToolCall, UsageMetadata, ResponseMetadata
from trustmodel_mcp.storage.sqlite import SQLiteStorage
from trustmodel_mcp.extractors.anthropic import AnthropicExtractor
from trustmodel_mcp.extractors.openai import OpenAIExtractor


async def test_models():
    """Test data models."""
    print("Testing data models...")

    # Create a trace
    trace = Trace.create(agent_id="test-agent", thread_id="thread-123")
    print(f"  Created trace: {trace.id}")

    # Add a human message
    trace.add_message(Message(type=MessageType.HUMAN, content="Hello!"))
    print(f"  Added human message")

    # Add an AI message with usage
    trace.add_message(Message(
        type=MessageType.AI,
        content="Hello! How can I help?",
        tool_calls=[ToolCall(id="tc1", name="search", args={"query": "test"})],
        usage_metadata=UsageMetadata(input_tokens=10, output_tokens=15, total_tokens=25),
        response_metadata=ResponseMetadata(model_name="claude-3", finish_reason="end_turn"),
    ))
    print(f"  Added AI message with tool call")

    # Check aggregation
    assert trace.total_tokens == 25, f"Expected 25 tokens, got {trace.total_tokens}"
    assert trace.tool_call_count == 1, f"Expected 1 tool call, got {trace.tool_call_count}"
    print(f"  Token tracking: {trace.total_tokens} tokens, {trace.tool_call_count} tool calls")

    # Test serialization
    trace_dict = trace.to_dict()
    assert len(trace_dict["messages"]) == 2
    print(f"  Serialization: {len(trace_dict['messages'])} messages")

    print("  Models: OK")


async def test_storage():
    """Test SQLite storage."""
    print("\nTesting SQLite storage...")

    # Use temp database
    storage = SQLiteStorage("/tmp/test_traces.db")
    await storage.initialize()
    print("  Initialized database")

    # Create and save a trace
    trace = Trace.create(agent_id="test-agent")
    trace.add_message(Message(type=MessageType.HUMAN, content="Test message"))
    trace.complete()

    await storage.save_trace(trace)
    print(f"  Saved trace: {trace.id}")

    # Retrieve it
    retrieved = await storage.get_trace(trace.id)
    assert retrieved is not None
    assert retrieved.id == trace.id
    assert len(retrieved.messages) == 1
    print(f"  Retrieved trace with {len(retrieved.messages)} message(s)")

    # List traces
    traces = await storage.list_traces(agent_id="test-agent")
    assert len(traces) >= 1
    print(f"  Listed {len(traces)} trace(s)")

    # Count
    count = await storage.count_traces(agent_id="test-agent")
    print(f"  Count: {count} traces")

    await storage.close()
    print("  Storage: OK")


async def test_anthropic_extractor():
    """Test Anthropic extractor."""
    print("\nTesting Anthropic extractor...")

    extractor = AnthropicExtractor()

    # Sample Anthropic request/response
    request = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 1024,
        "system": "You are a helpful assistant.",
        "messages": [
            {"role": "user", "content": "What is 2+2?"}
        ]
    }

    response = {
        "id": "msg_123",
        "type": "message",
        "role": "assistant",
        "content": [
            {"type": "text", "text": "2+2 equals 4."}
        ],
        "model": "claude-sonnet-4-20250514",
        "stop_reason": "end_turn",
        "usage": {
            "input_tokens": 25,
            "output_tokens": 10
        }
    }

    messages = extractor.extract_messages(request, response, latency_ms=500)

    assert len(messages) == 3  # system + human + ai
    assert messages[0].type == MessageType.SYSTEM
    assert messages[1].type == MessageType.HUMAN
    assert messages[2].type == MessageType.AI
    assert messages[2].usage_metadata.total_tokens == 35
    print(f"  Extracted {len(messages)} messages")
    print(f"  System: '{messages[0].content[:50]}...'")
    print(f"  Human: '{messages[1].content}'")
    print(f"  AI: '{messages[2].content}'")
    print(f"  Tokens: {messages[2].usage_metadata.total_tokens}")

    print("  Anthropic extractor: OK")


async def test_openai_extractor():
    """Test OpenAI extractor."""
    print("\nTesting OpenAI extractor...")

    extractor = OpenAIExtractor()

    # Sample OpenAI request/response
    request = {
        "model": "gpt-4",
        "messages": [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello!"}
        ]
    }

    response = {
        "id": "chatcmpl-123",
        "object": "chat.completion",
        "created": 1234567890,
        "model": "gpt-4",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Hello! How can I help?"
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": 20,
            "completion_tokens": 8,
            "total_tokens": 28
        }
    }

    messages = extractor.extract_messages(request, response, latency_ms=300)

    assert len(messages) == 3  # system + human + ai
    assert messages[0].type == MessageType.SYSTEM
    assert messages[1].type == MessageType.HUMAN
    assert messages[2].type == MessageType.AI
    assert messages[2].usage_metadata.total_tokens == 28
    print(f"  Extracted {len(messages)} messages")
    print(f"  Tokens: {messages[2].usage_metadata.total_tokens}")

    print("  OpenAI extractor: OK")


async def test_tool_calls():
    """Test tool call extraction."""
    print("\nTesting tool call extraction...")

    extractor = AnthropicExtractor()

    request = {
        "model": "claude-sonnet-4-20250514",
        "messages": [
            {"role": "user", "content": "Search for Python tutorials"}
        ],
        "tools": [{"name": "search", "description": "Search the web"}]
    }

    response = {
        "id": "msg_123",
        "type": "message",
        "role": "assistant",
        "content": [
            {"type": "text", "text": "I'll search for that."},
            {
                "type": "tool_use",
                "id": "tool_1",
                "name": "search",
                "input": {"query": "Python tutorials"}
            }
        ],
        "model": "claude-sonnet-4-20250514",
        "stop_reason": "tool_use",
        "usage": {"input_tokens": 30, "output_tokens": 20}
    }

    messages = extractor.extract_messages(request, response)

    ai_msg = messages[-1]
    assert ai_msg.tool_calls is not None
    assert len(ai_msg.tool_calls) == 1
    assert ai_msg.tool_calls[0].name == "search"
    assert ai_msg.tool_calls[0].args == {"query": "Python tutorials"}
    print(f"  Tool call: {ai_msg.tool_calls[0].name}({ai_msg.tool_calls[0].args})")

    print("  Tool call extraction: OK")


async def main():
    """Run all tests."""
    print("=" * 50)
    print("TrustModel MCP Tracing Server - Local Tests")
    print("=" * 50)

    await test_models()
    await test_storage()
    await test_anthropic_extractor()
    await test_openai_extractor()
    await test_tool_calls()

    print("\n" + "=" * 50)
    print("All tests passed!")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
