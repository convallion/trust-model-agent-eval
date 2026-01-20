# MCP Tracing Server Plan

## Overview

Build an MCP (Model Context Protocol) server that provides universal agent tracing capabilities. This server can be used by Claude Desktop, Claude Code, or any MCP-compatible client to automatically capture and store traces from any LLM provider.

## Why MCP?

1. **Native Claude Integration** - Works seamlessly with Claude Desktop and Claude Code
2. **Standardized Protocol** - MCP is becoming the standard for AI tool integration
3. **Easy Distribution** - Single package, easy to install and configure
4. **Extensible** - New providers can be added as MCP tools
5. **Bidirectional** - Can both capture traces AND query them

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Claude Desktop / Claude Code                     │
│                                                                      │
│  "Call the weather API"  ──▶  MCP Client  ──▶  Your Agent Code      │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    TrustModel MCP Tracing Server                     │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                         MCP Tools                            │    │
│  │                                                              │    │
│  │  • trace_llm_call      - Capture an LLM API call            │    │
│  │  • trace_tool_call     - Capture a tool execution           │    │
│  │  • start_trace         - Begin a new trace/conversation     │    │
│  │  • end_trace           - Complete a trace                   │    │
│  │  • get_traces          - Query stored traces                │    │
│  │  • get_trace_detail    - Get full trace with messages       │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                       MCP Resources                          │    │
│  │                                                              │    │
│  │  • traces://{agent_id}           - List traces for agent    │    │
│  │  • trace://{trace_id}            - Single trace details     │    │
│  │  • trace://{trace_id}/messages   - Trace messages           │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    Provider Extractors                       │    │
│  │                                                              │    │
│  │  • AnthropicExtractor  - Parse Claude API format            │    │
│  │  • OpenAIExtractor     - Parse GPT API format               │    │
│  │  • GenericExtractor    - Fallback for any provider          │    │
│  │  • [Extensible]        - Add new providers easily           │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                      Storage Backend                         │    │
│  │                                                              │    │
│  │  • SQLite (local)      - Default, zero config               │    │
│  │  • TrustModel API      - Send to TrustModel server          │    │
│  │  • File (JSON/JSONL)   - Simple file export                 │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## MCP Server Specification

### Server Info

```json
{
  "name": "trustmodel-tracing",
  "version": "1.0.0",
  "description": "Universal LLM tracing for any provider"
}
```

### Tools

#### 1. `trace_llm_call`
Capture a complete LLM API call (request + response).

```typescript
{
  name: "trace_llm_call",
  description: "Capture an LLM API call for tracing",
  inputSchema: {
    type: "object",
    properties: {
      agent_id: { type: "string", description: "Agent identifier" },
      provider: { type: "string", enum: ["anthropic", "openai", "generic"] },
      thread_id: { type: "string", description: "Conversation thread ID (optional)" },
      request: {
        type: "object",
        description: "The API request body",
        properties: {
          model: { type: "string" },
          messages: { type: "array" },
          // ... provider-specific fields
        }
      },
      response: {
        type: "object",
        description: "The API response body",
        properties: {
          content: { type: "array" },
          usage: { type: "object" },
          // ... provider-specific fields
        }
      },
      latency_ms: { type: "number", description: "Request latency in ms" }
    },
    required: ["agent_id", "provider", "request", "response"]
  }
}
```

#### 2. `trace_tool_call`
Capture a tool/function execution.

```typescript
{
  name: "trace_tool_call",
  description: "Capture a tool execution for tracing",
  inputSchema: {
    type: "object",
    properties: {
      agent_id: { type: "string" },
      thread_id: { type: "string" },
      tool_name: { type: "string" },
      tool_input: { type: "object" },
      tool_output: { type: "string" },
      latency_ms: { type: "number" },
      success: { type: "boolean" }
    },
    required: ["agent_id", "tool_name", "tool_input", "tool_output"]
  }
}
```

#### 3. `start_trace`
Begin a new trace/conversation.

```typescript
{
  name: "start_trace",
  description: "Start a new trace for a conversation",
  inputSchema: {
    type: "object",
    properties: {
      agent_id: { type: "string" },
      thread_id: { type: "string", description: "Custom thread ID (auto-generated if omitted)" },
      metadata: { type: "object", description: "Custom metadata" }
    },
    required: ["agent_id"]
  }
}
// Returns: { trace_id: "...", thread_id: "..." }
```

#### 4. `end_trace`
Complete a trace.

```typescript
{
  name: "end_trace",
  description: "End and finalize a trace",
  inputSchema: {
    type: "object",
    properties: {
      trace_id: { type: "string" },
      status: { type: "string", enum: ["completed", "failed", "cancelled"] },
      error_message: { type: "string" }
    },
    required: ["trace_id"]
  }
}
```

#### 5. `get_traces`
Query stored traces.

```typescript
{
  name: "get_traces",
  description: "List traces with optional filters",
  inputSchema: {
    type: "object",
    properties: {
      agent_id: { type: "string" },
      limit: { type: "number", default: 20 },
      offset: { type: "number", default: 0 },
      status: { type: "string", enum: ["running", "completed", "failed"] }
    }
  }
}
// Returns: { traces: [...], total: number }
```

#### 6. `get_trace_detail`
Get full trace with all messages.

```typescript
{
  name: "get_trace_detail",
  description: "Get complete trace details including all messages",
  inputSchema: {
    type: "object",
    properties: {
      trace_id: { type: "string" }
    },
    required: ["trace_id"]
  }
}
// Returns: Full trace object matching LangSmith format
```

### Resources

```typescript
// List traces for an agent
"traces://{agent_id}"
// Returns: JSON array of trace summaries

// Get single trace
"trace://{trace_id}"
// Returns: Full trace object

// Get trace messages only
"trace://{trace_id}/messages"
// Returns: Array of messages in LangSmith format
```

### Prompts (Optional)

```typescript
// Analyze trace for issues
{
  name: "analyze_trace",
  description: "Analyze a trace for performance or quality issues",
  arguments: [
    { name: "trace_id", required: true }
  ]
}
```

---

## Data Model

### Trace (matches LangSmith format)

```typescript
interface Trace {
  id: string;
  thread_id: string;
  agent_id: string;
  created_at: string;
  updated_at: string;
  status: "running" | "completed" | "failed";

  // Messages in LangSmith-compatible format
  messages: Message[];

  // Aggregated stats
  total_tokens: number;
  total_input_tokens: number;
  total_output_tokens: number;
  tool_call_count: number;
  latency_ms: number;

  // Metadata
  metadata: Record<string, any>;
}

interface Message {
  type: "human" | "ai" | "tool" | "system";
  content: string;
  name?: string;
  tool_calls?: ToolCall[];
  tool_call_id?: string;
  usage_metadata?: {
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
  };
  response_metadata?: {
    model_name?: string;
    finish_reason?: string;
  };
}

interface ToolCall {
  id: string;
  name: string;
  args: Record<string, any>;
}
```

---

## File Structure

```
mcp-tracing-server/
├── pyproject.toml              # Package config
├── README.md                   # Documentation
├── src/
│   └── trustmodel_mcp/
│       ├── __init__.py
│       ├── server.py           # MCP server entry point
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── trace_llm.py    # trace_llm_call tool
│       │   ├── trace_tool.py   # trace_tool_call tool
│       │   ├── trace_lifecycle.py  # start/end trace
│       │   └── query.py        # get_traces, get_trace_detail
│       ├── resources/
│       │   ├── __init__.py
│       │   └── traces.py       # Resource handlers
│       ├── extractors/
│       │   ├── __init__.py
│       │   ├── base.py         # BaseExtractor
│       │   ├── anthropic.py    # AnthropicExtractor
│       │   ├── openai.py       # OpenAIExtractor
│       │   └── generic.py      # GenericExtractor
│       ├── storage/
│       │   ├── __init__.py
│       │   ├── base.py         # StorageBackend interface
│       │   ├── sqlite.py       # SQLite storage
│       │   ├── api.py          # TrustModel API storage
│       │   └── file.py         # File-based storage
│       └── models.py           # Data models
└── tests/
    ├── test_extractors.py
    ├── test_storage.py
    └── test_tools.py
```

---

## Configuration

### Claude Desktop (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "trustmodel-tracing": {
      "command": "uvx",
      "args": ["trustmodel-mcp"],
      "env": {
        "TRUSTMODEL_AGENT_ID": "my-agent-id",
        "TRUSTMODEL_API_KEY": "optional-for-cloud-sync",
        "TRUSTMODEL_STORAGE": "sqlite"  // or "api" or "file"
      }
    }
  }
}
```

### Environment Variables

```bash
# Required
TRUSTMODEL_AGENT_ID=my-agent-id

# Optional - for cloud sync
TRUSTMODEL_API_URL=http://localhost:8000
TRUSTMODEL_API_KEY=your-api-key

# Optional - storage config
TRUSTMODEL_STORAGE=sqlite          # sqlite, api, file
TRUSTMODEL_DB_PATH=~/.trustmodel/traces.db
TRUSTMODEL_FILE_PATH=~/.trustmodel/traces.jsonl
```

---

## Implementation Phases

### Phase 1: Core MCP Server
1. Set up MCP server skeleton with `mcp` package
2. Implement `trace_llm_call` tool
3. Implement SQLite storage backend
4. Add Anthropic extractor
5. Add OpenAI extractor

### Phase 2: Full Tool Suite
6. Implement `start_trace` / `end_trace`
7. Implement `trace_tool_call`
8. Implement `get_traces` / `get_trace_detail`
9. Add MCP resources

### Phase 3: Storage & Sync
10. Add TrustModel API storage backend
11. Add file-based storage
12. Implement sync between local and cloud

### Phase 4: Integration
13. Update TrustModel frontend to display MCP traces
14. Add trace comparison with LangSmith
15. Documentation and examples

---

## Usage Examples

### Example 1: Auto-trace Claude calls

```python
# In your agent code, after each Claude API call:
import anthropic
from mcp import Client

mcp = Client("trustmodel-tracing")
client = anthropic.Anthropic()

# Make API call
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hello!"}]
)

# Trace it
await mcp.call_tool("trace_llm_call", {
    "agent_id": "my-agent",
    "provider": "anthropic",
    "request": {"model": "claude-sonnet-4-20250514", "messages": [...]},
    "response": response.model_dump(),
    "latency_ms": 1234
})
```

### Example 2: Query traces

```python
# Get recent traces
traces = await mcp.call_tool("get_traces", {
    "agent_id": "my-agent",
    "limit": 10
})

# Get full trace detail
detail = await mcp.call_tool("get_trace_detail", {
    "trace_id": traces[0]["id"]
})

# detail.messages is in same format as LangSmith!
```

### Example 3: Use with Claude Code

Claude Code can automatically use the MCP server:

```
User: "Trace this conversation and show me the token usage"

Claude: I'll use the trustmodel-tracing MCP server to capture this.
[Calls trace_llm_call with the conversation]
[Calls get_trace_detail to show stats]

Here's the trace:
- Total tokens: 1,234
- Input: 500, Output: 734
- Model: claude-sonnet-4-20250514
```

---

## Benefits Over Proxy Approach

| Aspect | MCP Server | Proxy |
|--------|-----------|-------|
| Setup | Add to config.json | Change BASE_URL |
| Claude Integration | Native | Manual |
| Streaming | Full support | Complex |
| Tool calls | Native capture | Parse from response |
| Offline | Works locally | Needs proxy running |
| Distribution | `uvx trustmodel-mcp` | Docker/binary |

---

## Next Steps

1. **Approve this plan** - Confirm the approach
2. **Create MCP server skeleton** - Basic server with one tool
3. **Implement extractors** - Anthropic + OpenAI
4. **Add storage** - SQLite first
5. **Test with Claude Desktop** - End-to-end validation
6. **Integrate with TrustModel UI** - Display traces
