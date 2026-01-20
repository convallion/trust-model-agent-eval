# Universal Agent Tracing Implementation Plan

## Goal
Capture the same level of trace detail for Claude/OpenAI/any LLM agents as we get from LangSmith:
- Full conversation history with messages
- Tool calls with input args and output responses
- Token usage (input, output, total)
- Model name, timestamps, latency
- Hierarchical span structure

## Current State
- LangGraph/LangSmith: Full integration via `/threads/search` API
- Claude/OpenAI: SDK has auto-instrumentation code but not connected end-to-end
- Proxy exists in SDK CLI but incomplete

---

## Approach: Enhanced Proxy + SDK Auto-Instrumentation

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Your Agent Code                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │  Anthropic  │  │   OpenAI    │  │  Any LLM    │              │
│  │    SDK      │  │    SDK      │  │    SDK      │              │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │
└─────────┼────────────────┼────────────────┼─────────────────────┘
          │                │                │
          ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────┐
│                   TrustModel Trace Proxy                         │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  • Intercepts all LLM API calls                          │   │
│  │  • Extracts messages, tool_calls, usage                  │   │
│  │  • Forwards to real API                                  │   │
│  │  • Sends traces to TrustModel server                     │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────┐
│                   TrustModel Server                              │
│  POST /v1/traces/ingest  ──▶  Same format as LangSmith          │
└─────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Playground UI                                  │
│  Same trace detail view for ALL providers                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## Implementation Steps

### Phase 1: Backend Trace Ingestion (Server)

#### 1.1 Create unified trace format schema
**File:** `server/app/schemas/trace_ingest.py`

```python
class MessageIngest(BaseModel):
    type: str  # "human", "ai", "tool", "system"
    content: str
    name: Optional[str] = None
    tool_calls: Optional[List[ToolCallIngest]] = None
    tool_call_id: Optional[str] = None
    usage_metadata: Optional[UsageMetadata] = None
    response_metadata: Optional[ResponseMetadata] = None

class ToolCallIngest(BaseModel):
    id: str
    name: str
    args: Dict[str, Any]

class UsageMetadata(BaseModel):
    input_tokens: int
    output_tokens: int
    total_tokens: int

class ResponseMetadata(BaseModel):
    model_name: Optional[str] = None
    finish_reason: Optional[str] = None
    latency_ms: Optional[float] = None

class TraceIngestRequest(BaseModel):
    agent_id: UUID
    thread_id: Optional[str] = None  # For conversation continuity
    messages: List[MessageIngest]
    metadata: Optional[Dict[str, Any]] = None
```

#### 1.2 Create trace ingestion endpoint
**File:** `server/app/api/v1/traces.py` (add endpoint)

```python
@router.post("/ingest")
async def ingest_trace(
    data: TraceIngestRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Ingest trace data from any provider in unified format."""
    # Converts to internal Trace + Span models
    # Stores in same format as LangSmith traces
```

---

### Phase 2: Trace Proxy Server (New Component)

#### 2.1 Create standalone proxy server
**File:** `server/app/proxy/server.py`

Features:
- HTTP server on configurable port (default 8080)
- Routes for Anthropic (`/v1/messages`)
- Routes for OpenAI (`/v1/chat/completions`)
- Extracts trace data before forwarding
- Async trace submission to TrustModel server

#### 2.2 Anthropic message extraction
**File:** `server/app/proxy/extractors/anthropic.py`

```python
def extract_anthropic_trace(request_body, response_body) -> TraceIngestRequest:
    messages = []

    # Extract user messages from request
    for msg in request_body.get("messages", []):
        messages.append({
            "type": "human" if msg["role"] == "user" else "system",
            "content": extract_content(msg["content"])
        })

    # Extract AI response
    response_content = response_body.get("content", [])
    tool_calls = extract_tool_calls(response_content)

    messages.append({
        "type": "ai",
        "content": extract_text_content(response_content),
        "tool_calls": tool_calls,
        "usage_metadata": {
            "input_tokens": response_body["usage"]["input_tokens"],
            "output_tokens": response_body["usage"]["output_tokens"],
            "total_tokens": sum(response_body["usage"].values())
        },
        "response_metadata": {
            "model_name": response_body.get("model"),
            "finish_reason": response_body.get("stop_reason")
        }
    })

    return messages
```

#### 2.3 OpenAI message extraction
**File:** `server/app/proxy/extractors/openai.py`

Similar extraction for OpenAI format.

---

### Phase 3: Frontend Integration

#### 3.1 Update trace fetching to support both sources
**File:** `playground/src/app/api/fetch-traces/route.ts`

```typescript
// Fetch from LangSmith OR TrustModel server based on agent config
if (agent.framework === "langsmith") {
  // Existing LangSmith fetch
} else {
  // Fetch from TrustModel /v1/traces?agent_id=...
}
```

#### 3.2 Normalize trace format
Both sources should return same structure:
```typescript
interface UnifiedTrace {
  id: string;
  created_at: string;
  updated_at: string;
  status: string;
  messages: Message[];
  metadata: Record<string, any>;
}
```

---

### Phase 4: Easy Setup for Users

#### 4.1 One-line proxy setup
```bash
# Start proxy
trustmodel proxy start --port 8080

# Or via Docker
docker run -p 8080:8080 trustmodel/proxy
```

#### 4.2 Environment variable setup
```bash
# For Anthropic
export ANTHROPIC_BASE_URL=http://localhost:8080/anthropic

# For OpenAI
export OPENAI_BASE_URL=http://localhost:8080/openai
```

#### 4.3 SDK auto-instrumentation (alternative)
```python
from trustmodel import instrument

# One-line setup - patches Anthropic/OpenAI SDKs
instrument(agent_id="your-agent-id", api_key="your-key")

# Your existing code works unchanged
from anthropic import Anthropic
client = Anthropic()
response = client.messages.create(...)  # Automatically traced!
```

---

## File Changes Summary

### New Files
| File | Purpose |
|------|---------|
| `server/app/schemas/trace_ingest.py` | Unified trace ingest schema |
| `server/app/proxy/__init__.py` | Proxy module |
| `server/app/proxy/server.py` | Proxy HTTP server |
| `server/app/proxy/extractors/anthropic.py` | Anthropic format extraction |
| `server/app/proxy/extractors/openai.py` | OpenAI format extraction |
| `server/app/proxy/extractors/base.py` | Base extractor class |

### Modified Files
| File | Changes |
|------|---------|
| `server/app/api/v1/traces.py` | Add `/ingest` endpoint |
| `server/app/services/trace_service.py` | Add `ingest_messages()` method |
| `playground/src/app/api/fetch-traces/route.ts` | Support both LangSmith and TrustModel sources |
| `playground/src/app/agents/[id]/page.tsx` | Auto-detect trace source |

---

## Implementation Order

1. **Backend trace ingest endpoint** - Accept unified format
2. **Anthropic proxy extractor** - Parse Anthropic requests/responses
3. **OpenAI proxy extractor** - Parse OpenAI requests/responses
4. **Proxy server** - HTTP server that intercepts and forwards
5. **Frontend integration** - Fetch and display traces from TrustModel
6. **SDK integration** - Connect existing auto-instrumentation
7. **Docker/CLI** - Easy deployment options

---

## Verification

### Test Anthropic Tracing
```python
import anthropic

# Point to proxy
client = anthropic.Anthropic(base_url="http://localhost:8080/anthropic")

response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hello!"}]
)

# Check trace appears in UI
```

### Test OpenAI Tracing
```python
import openai

client = openai.OpenAI(base_url="http://localhost:8080/openai")

response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello!"}]
)

# Check trace appears in UI
```
