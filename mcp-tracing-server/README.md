# TrustModel MCP Tracing Server

Universal LLM tracing for any provider via MCP protocol. Captures traces in LangSmith-compatible format.

## Features

- **Universal Tracing**: Capture traces from Claude, OpenAI, and any LLM provider
- **LangSmith Compatible**: Same message format as LangSmith (human, ai, tool messages)
- **Token Tracking**: Automatic input/output token counting
- **Tool Call Tracking**: Full tool call and response capture
- **Local Storage**: SQLite database with zero configuration
- **MCP Native**: Works seamlessly with Claude Desktop and Claude Code

## Installation

```bash
# Using uvx (recommended)
uvx trustmodel-mcp

# Or install with pip
pip install trustmodel-mcp
```

## Quick Start

### 1. Add to Claude Desktop

Edit your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "trustmodel-tracing": {
      "command": "uvx",
      "args": ["trustmodel-mcp"]
    }
  }
}
```

### 2. Capture Traces

The server provides these tools:

| Tool | Description |
|------|-------------|
| `trace_llm_call` | Capture an LLM API call (request + response) |
| `trace_tool_call` | Capture a tool execution |
| `start_trace` | Begin a new trace/conversation |
| `end_trace` | Complete a trace |
| `get_traces` | List stored traces |
| `get_trace_detail` | Get full trace with messages |

### 3. Example Usage

```python
# After making a Claude API call, trace it:
await mcp.call_tool("trace_llm_call", {
    "agent_id": "my-agent",
    "provider": "anthropic",
    "request": {
        "model": "claude-sonnet-4-20250514",
        "messages": [{"role": "user", "content": "Hello!"}]
    },
    "response": response.model_dump(),
    "latency_ms": 1234
})

# Query traces
traces = await mcp.call_tool("get_traces", {
    "agent_id": "my-agent",
    "limit": 10
})

# Get full trace detail
detail = await mcp.call_tool("get_trace_detail", {
    "trace_id": "..."
})
```

## Supported Providers

### Out of the box:
- **Anthropic** (Claude) - Full support for Messages API
- **OpenAI** (GPT) - Full support for Chat Completions API

### Extensible:
Add new providers by implementing the `BaseExtractor` interface.

## Data Format

Traces are stored in LangSmith-compatible format:

```json
{
  "id": "trace-uuid",
  "thread_id": "thread-uuid",
  "agent_id": "my-agent",
  "status": "completed",
  "messages": [
    {
      "type": "human",
      "content": "Hello!"
    },
    {
      "type": "ai",
      "content": "Hello! How can I help you today?",
      "usage_metadata": {
        "input_tokens": 10,
        "output_tokens": 15,
        "total_tokens": 25
      },
      "response_metadata": {
        "model_name": "claude-sonnet-4-20250514",
        "finish_reason": "end_turn"
      }
    }
  ],
  "total_tokens": 25,
  "tool_call_count": 0,
  "latency_ms": 1234
}
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TRUSTMODEL_DB_PATH` | SQLite database path | `~/.trustmodel/traces.db` |
| `TRUSTMODEL_AGENT_ID` | Default agent ID | (none) |

## Development

```bash
# Clone the repo
git clone https://github.com/trustmodel/mcp-tracing-server
cd mcp-tracing-server

# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run server locally
python -m trustmodel_mcp.server
```

## License

MIT
