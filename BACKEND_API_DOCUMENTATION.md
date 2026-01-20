# TrustModel Agent Eval - Backend API Documentation

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Authentication](#authentication)
4. [Next.js API Routes (Frontend Proxy)](#nextjs-api-routes)
5. [FastAPI Backend Endpoints](#fastapi-backend-endpoints)
6. [WebSocket Endpoints](#websocket-endpoints)
7. [Frontend vs Programmatic Access](#frontend-vs-programmatic-access)
8. [Examples](#examples)

---

## Overview

TrustModel Agent Eval provides two API layers:

| Layer | Technology | Port | Purpose |
|-------|------------|------|---------|
| **Frontend API** | Next.js API Routes | 3000 | Browser-friendly endpoints, proxying, trace fetching |
| **Backend API** | FastAPI | 8000 | Core business logic, database operations, evaluations |

**Base URLs:**
- Frontend: `http://localhost:3000/api`
- Backend: `http://localhost:8000/v1`

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Browser / Client                          │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Next.js Frontend (Port 3000)                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    /api/* Routes                            ││
│  │  • /api/fetch-traces     - Fetch from LangGraph             ││
│  │  • /api/test-agent       - Test agent connectivity          ││
│  │  • /api/chat-agent       - Chat with LangGraph agents       ││
│  │  • /api/proxy/anthropic  - Anthropic API proxy              ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI Backend (Port 8000)                   │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                      /v1/* Routes                           ││
│  │  • /v1/agents        - Agent CRUD                           ││
│  │  • /v1/traces        - Trace management                     ││
│  │  • /v1/evaluations   - Run evaluations                      ││
│  │  • /v1/certificates  - Trust certificates                   ││
│  │  • /v1/sessions      - TACP protocol sessions               ││
│  │  • /v1/registry      - Public trust registry                ││
│  │  • /v1/stats         - Analytics & metrics                  ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                        PostgreSQL Database                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## Authentication

### Backend API (FastAPI)

All endpoints except `/v1/registry/*` require authentication via Bearer token.

```bash
# Header format
Authorization: Bearer <your-api-token>
```

**Get a token:**
```bash
# Login endpoint (if implemented)
POST /v1/auth/login
{
  "email": "user@example.com",
  "password": "your-password"
}
```

### Frontend API (Next.js)

Frontend routes handle authentication internally or accept keys in request body.

---

## Next.js API Routes

### 1. Test Agent Connection

**Endpoint:** `POST /api/test-agent`

Tests connectivity to a LangGraph/LangSmith agent.

**Request:**
```json
{
  "url": "https://your-agent.us.langgraph.app",
  "apiKey": "lsv2_pt_xxx" // optional
}
```

**Response:**
```json
{
  "success": true,
  "message": "Successfully connected to agent",
  "details": "Found 3 assistants"
}
```

**Use Case:** Validate agent URL before registration.

---

### 2. Fetch Traces from LangGraph

**Endpoint:** `POST /api/fetch-traces`

Fetches conversation threads/traces from LangGraph Cloud.

**Request:**
```json
{
  "url": "https://your-agent.us.langgraph.app",
  "apiKey": "lsv2_pt_xxx",
  "limit": 20
}
```

**Response:**
```json
{
  "success": true,
  "traces": [
    {
      "id": "thread-uuid",
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-15T10:35:00Z",
      "status": "idle",
      "messages": [
        {
          "type": "human",
          "content": "What's on my calendar?"
        },
        {
          "type": "ai",
          "content": "Let me check your calendar...",
          "tool_calls": [
            {
              "name": "get_calendar_events",
              "args": {"date": "today"},
              "id": "call_123"
            }
          ],
          "usage_metadata": {
            "input_tokens": 150,
            "output_tokens": 200,
            "total_tokens": 350
          }
        },
        {
          "type": "tool",
          "content": "{\"events\": [...]}",
          "tool_call_id": "call_123"
        }
      ],
      "lastMessage": "You have 3 meetings today..."
    }
  ],
  "total": 15
}
```

**Use Case:** No-code trace viewing for LangSmith agents.

---

### 3. Chat with Agent

**Endpoint:** `POST /api/chat-agent`

Send messages to a LangGraph agent.

**Request:**
```json
{
  "url": "https://your-agent.us.langgraph.app",
  "apiKey": "lsv2_pt_xxx",
  "message": "Hello, what can you do?",
  "threadId": "existing-thread-id" // optional
}
```

**Response:**
```json
{
  "success": true,
  "threadId": "new-or-existing-thread-id",
  "response": "I can help you with...",
  "messages": [
    {"role": "user", "content": "Hello, what can you do?"},
    {"role": "assistant", "content": "I can help you with..."}
  ]
}
```

**Note:** Requires write permissions on API key.

---

### 4. Anthropic API Proxy

**Endpoint:** `POST /api/proxy/anthropic/{path}`

Proxies requests to Anthropic API while capturing traces.

**Request:**
```bash
curl -X POST http://localhost:3000/api/proxy/anthropic/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: sk-ant-xxx" \
  -H "x-trustmodel-agent-id: your-agent-uuid" \
  -d '{
    "model": "claude-3-sonnet-20240229",
    "max_tokens": 1024,
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

**Response:** Standard Anthropic API response

**Use Case:**
- Set `ANTHROPIC_BASE_URL=http://localhost:3000/api/proxy/anthropic` in your app
- All Claude calls are automatically traced

---

## FastAPI Backend Endpoints

### Agents API

#### Create Agent
```bash
POST /v1/agents
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "My Calendar Agent",
  "description": "Manages calendar events",
  "framework": "langsmith",
  "metadata": {
    "langsmith_api_url": "https://xxx.us.langgraph.app",
    "langsmith_api_key": "lsv2_pt_xxx"
  }
}
```

**Response:**
```json
{
  "id": "uuid",
  "name": "My Calendar Agent",
  "description": "Manages calendar events",
  "framework": "langsmith",
  "status": "active",
  "organization_id": "org-uuid",
  "created_at": "2024-01-15T10:00:00Z",
  "stats": {
    "total_traces": 0,
    "total_evaluations": 0,
    "last_evaluation": null,
    "trust_score": null
  }
}
```

#### List Agents
```bash
GET /v1/agents?page=1&page_size=20&status=active
Authorization: Bearer <token>
```

#### Get Agent
```bash
GET /v1/agents/{agent_id}
Authorization: Bearer <token>
```

#### Update Agent
```bash
PATCH /v1/agents/{agent_id}
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "Updated Name",
  "description": "Updated description"
}
```

#### Delete Agent
```bash
DELETE /v1/agents/{agent_id}
Authorization: Bearer <token>
```

---

### Traces API

#### Ingest Traces (Batch)
```bash
POST /v1/traces/batch
Authorization: Bearer <token>
Content-Type: application/json

{
  "traces": [
    {
      "agent_id": "uuid",
      "trace_id": "custom-id-or-auto",
      "spans": [...],
      "metadata": {}
    }
  ]
}
```

#### Ingest Single Trace
```bash
POST /v1/traces/ingest
Authorization: Bearer <token>
Content-Type: application/json

{
  "agent_id": "uuid",
  "trace_id": "optional-custom-id",
  "spans": [
    {
      "span_type": "llm",
      "name": "claude-3-sonnet",
      "started_at": "2024-01-15T10:00:00Z",
      "ended_at": "2024-01-15T10:00:02Z",
      "status": "ok",
      "attributes": {
        "model": "claude-3-sonnet",
        "input_tokens": 150,
        "output_tokens": 200
      }
    }
  ],
  "metadata": {
    "session_id": "user-session-123"
  }
}
```

**Response:**
```json
{
  "trace_id": "generated-uuid",
  "spans_created": 1,
  "message": "Trace ingested successfully"
}
```

#### List Traces
```bash
GET /v1/traces?agent_id={uuid}&page=1&page_size=20
Authorization: Bearer <token>
```

#### Get Trace with Spans
```bash
GET /v1/traces/{trace_id}?include_spans=true
Authorization: Bearer <token>
```

#### Delete Trace
```bash
DELETE /v1/traces/{trace_id}
Authorization: Bearer <token>
```

---

### Evaluations API

#### Start Evaluation
```bash
POST /v1/evaluations
Authorization: Bearer <token>
Content-Type: application/json

{
  "agent_id": "uuid",
  "suites": ["capability", "safety", "reliability", "communication"]
}
```

**Response:**
```json
{
  "id": "eval-uuid",
  "agent_id": "agent-uuid",
  "status": "running",
  "started_at": "2024-01-15T10:00:00Z",
  "suites": ["capability", "safety", "reliability", "communication"],
  "results": null
}
```

#### List Evaluations
```bash
GET /v1/evaluations?agent_id={uuid}&status=completed&page=1
Authorization: Bearer <token>
```

#### Get Evaluation Results
```bash
GET /v1/evaluations/{evaluation_id}
Authorization: Bearer <token>
```

**Response:**
```json
{
  "id": "eval-uuid",
  "agent_id": "agent-uuid",
  "status": "completed",
  "started_at": "2024-01-15T10:00:00Z",
  "completed_at": "2024-01-15T10:05:00Z",
  "results": {
    "overall_score": 0.85,
    "grade": "B",
    "suites": {
      "capability": {
        "score": 0.90,
        "tests": [
          {"name": "task_completion", "passed": true, "score": 0.95},
          {"name": "reasoning_quality", "passed": true, "score": 0.85}
        ]
      },
      "safety": {
        "score": 0.80,
        "tests": [
          {"name": "jailbreak_resistance", "passed": true, "score": 0.80},
          {"name": "boundary_respect", "passed": true, "score": 0.80}
        ]
      }
    }
  }
}
```

#### Get Suite Details
```bash
GET /v1/evaluations/{evaluation_id}/suites/capability
Authorization: Bearer <token>
```

#### Cancel Evaluation
```bash
POST /v1/evaluations/{evaluation_id}/cancel
Authorization: Bearer <token>
```

---

### Certificates API

#### Issue Certificate
```bash
POST /v1/certificates
Authorization: Bearer <token>
Content-Type: application/json

{
  "agent_id": "uuid",
  "evaluation_id": "eval-uuid",
  "validity_days": 90
}
```

#### List Certificates
```bash
GET /v1/certificates?agent_id={uuid}&status=active
Authorization: Bearer <token>
```

#### Get Certificate
```bash
GET /v1/certificates/{certificate_id}
Authorization: Bearer <token>
```

#### Verify Certificate (Public)
```bash
GET /v1/certificates/{certificate_id}/verify
# No auth required
```

**Response:**
```json
{
  "valid": true,
  "certificate_id": "cert-uuid",
  "agent_id": "agent-uuid",
  "agent_name": "My Agent",
  "grade": "B",
  "issued_at": "2024-01-15T10:00:00Z",
  "expires_at": "2024-04-15T10:00:00Z",
  "issuer": "TrustModel Registry"
}
```

#### Revoke Certificate
```bash
POST /v1/certificates/{certificate_id}/revoke
Authorization: Bearer <token>
Content-Type: application/json

{
  "reason": "Security vulnerability discovered"
}
```

#### Get Certificate Chain
```bash
GET /v1/certificates/{certificate_id}/chain
# No auth required
```

---

### Sessions API (TACP Protocol)

#### Create Session
```bash
POST /v1/sessions
Authorization: Bearer <token>
Content-Type: application/json

{
  "initiator_agent_id": "agent-1-uuid",
  "responder_agent_id": "agent-2-uuid"
}
```

#### List Sessions
```bash
GET /v1/sessions?agent_id={uuid}&status=active
Authorization: Bearer <token>
```

#### Accept Session
```bash
POST /v1/sessions/{session_id}/accept
Authorization: Bearer <token>
```

#### Reject Session
```bash
POST /v1/sessions/{session_id}/reject
Authorization: Bearer <token>
```

#### Send Message
```bash
POST /v1/sessions/{session_id}/messages
Authorization: Bearer <token>
Content-Type: application/json

{
  "message_type": "task_request",
  "payload": {
    "task": "analyze_data",
    "parameters": {...}
  }
}
```

#### End Session
```bash
DELETE /v1/sessions/{session_id}
Authorization: Bearer <token>
```

---

### Public Registry API

All registry endpoints are public (no authentication required).

#### Get Registry Info
```bash
GET /v1/registry
```

#### Search Certified Agents
```bash
GET /v1/registry/search?min_grade=B&capabilities=calendar,email
```

**Response:**
```json
{
  "agents": [
    {
      "id": "uuid",
      "name": "Calendar Agent",
      "organization": "Acme Corp",
      "grade": "A",
      "capabilities": ["calendar", "scheduling"],
      "certificate_id": "cert-uuid",
      "verified_at": "2024-01-15T10:00:00Z"
    }
  ],
  "total": 25,
  "page": 1,
  "page_size": 20
}
```

#### Get Agent Public Profile
```bash
GET /v1/registry/agents/{agent_id}
```

#### Get Certificate Revocation List
```bash
GET /v1/registry/crl
```

#### List Recognized Capabilities
```bash
GET /v1/registry/capabilities
```

#### Get Grade Definitions
```bash
GET /v1/registry/grades
```

**Response:**
```json
{
  "grades": {
    "A": {"min_score": 0.90, "description": "Excellent - Highly trusted"},
    "B": {"min_score": 0.80, "description": "Good - Trusted"},
    "C": {"min_score": 0.70, "description": "Acceptable - Basic trust"},
    "D": {"min_score": 0.60, "description": "Poor - Limited trust"},
    "F": {"min_score": 0.00, "description": "Failing - Not trusted"}
  }
}
```

---

### Stats API

#### Dashboard Stats
```bash
GET /v1/stats/dashboard
Authorization: Bearer <token>
```

**Response:**
```json
{
  "total_agents": 12,
  "active_agents": 10,
  "total_traces": 1500,
  "total_evaluations": 45,
  "completed_evaluations": 42,
  "total_certificates": 8,
  "active_certificates": 6,
  "avg_trust_score": 0.82,
  "agents_by_grade": {
    "A": 2,
    "B": 4,
    "C": 2,
    "D": 0,
    "F": 0
  }
}
```

#### Observability Metrics
```bash
GET /v1/stats/observability?hours=24&agent_id={uuid}
Authorization: Bearer <token>
```

#### Agent Stats
```bash
GET /v1/stats/agents/{agent_id}
Authorization: Bearer <token>
```

---

### Chat API

#### Chat with Agent
```bash
POST /v1/chat
Authorization: Bearer <token>
Content-Type: application/json

{
  "agent_id": "uuid",
  "messages": [
    {"role": "user", "content": "What's on my calendar today?"}
  ],
  "max_tokens": 1024
}
```

**Response:**
```json
{
  "id": "msg-uuid",
  "agent_id": "uuid",
  "content": "You have 3 meetings scheduled...",
  "role": "assistant",
  "trace_id": "trace-uuid",
  "latency_ms": 1250,
  "status": "success",
  "tool_calls": [
    {
      "name": "get_calendar",
      "success": true,
      "duration_ms": 150
    }
  ],
  "model": "claude-3-sonnet",
  "tokens_used": 450
}
```

---

## WebSocket Endpoints

### 1. Trace Streaming

**Endpoint:** `WS /v1/traces/stream?token=<auth-token>`

Real-time trace updates for your organization.

**Events:**
```json
// Connection confirmed
{"type": "connected", "organization_id": "uuid"}

// New trace started
{"type": "trace_started", "trace_id": "uuid", "agent_id": "uuid"}

// Span added
{"type": "span_added", "trace_id": "uuid", "span": {...}}

// Trace completed
{"type": "trace_completed", "trace_id": "uuid", "duration_ms": 1500}

// Keep-alive
{"type": "ping"}
```

---

### 2. Session WebSocket (TACP)

**Endpoint:** `WS /v1/sessions/{session_id}/ws`

Real-time communication between agents.

**TACP Protocol Messages:**
```json
// Trust challenge
{"type": "trust_challenge", "nonce": "random-string", "certificate_id": "uuid"}

// Trust proof
{"type": "trust_proof", "signed_nonce": "signature", "certificate_chain": [...]}

// Task request
{"type": "task_request", "task_id": "uuid", "task": "analyze", "parameters": {...}}

// Task progress
{"type": "task_progress", "task_id": "uuid", "progress": 0.5, "status": "running"}

// Task complete
{"type": "task_complete", "task_id": "uuid", "result": {...}}
```

---

### 3. Terminal WebSocket

**Endpoint:** `WS /v1/terminal?token=<auth-token>`

Interactive terminal session.

**Client → Server:**
```json
{"type": "input", "data": "ls -la\n"}
{"type": "resize", "rows": 24, "cols": 80}
```

**Server → Client:**
```json
{"type": "output", "data": "total 48\ndrwxr-xr-x..."}
{"type": "error", "message": "Command not found"}
```

---

## Frontend vs Programmatic Access

| Feature | Frontend (UI) | Programmatic (API) |
|---------|--------------|-------------------|
| **Register Agent** | ✅ Add Agent form | ✅ `POST /v1/agents` |
| **View Agents** | ✅ Home page list | ✅ `GET /v1/agents` |
| **Fetch LangGraph Traces** | ✅ "Fetch Traces" button | ✅ `POST /api/fetch-traces` |
| **View Trace Details** | ✅ Click trace → modal | ✅ `GET /v1/traces/{id}` |
| **Run Evaluation** | ✅ "Run Evaluation" button | ✅ `POST /v1/evaluations` |
| **View Evaluation Results** | ✅ Expandable cards | ✅ `GET /v1/evaluations/{id}` |
| **Issue Certificate** | ✅ Certificates tab | ✅ `POST /v1/certificates` |
| **View Certificates** | ✅ Certificates tab | ✅ `GET /v1/certificates` |
| **Revoke Certificate** | ✅ Certificates tab | ✅ `POST /v1/certificates/{id}/revoke` |
| **Copy Certificate ID** | ✅ Click to copy | N/A |
| **Verify Certificate** | ❌ Not in UI | ✅ `GET /v1/certificates/{id}/verify` |
| **Search Registry** | ❌ Not in UI | ✅ `GET /v1/registry/search` |
| **Create TACP Session** | ❌ Not in UI | ✅ `POST /v1/sessions` |
| **Real-time Trace Stream** | ❌ Not in UI | ✅ `WS /v1/traces/stream` |
| **Dashboard Stats** | ❌ Not in UI | ✅ `GET /v1/stats/dashboard` |
| **Anthropic Proxy Traces** | ✅ Setup instructions | ✅ Configure `ANTHROPIC_BASE_URL` |

---

## Trust Certificates (New!)

The Certificates tab in the agent detail page allows you to:

### Issue a Certificate
1. Run an evaluation on your agent (Evaluations tab → Run Evaluation)
2. Wait for the evaluation to complete
3. Go to Certificates tab → Click "Issue Certificate"
4. Select a completed evaluation
5. Certificate is issued with scores, capabilities, and safety attestations

### Certificate Details
Each certificate includes:
- **Certificate ID** - Unique identifier for agent collaboration (TACP protocol)
- **Grade** - A-F based on overall evaluation score
- **Scores** - Overall, capability, safety, reliability scores
- **Certified Capabilities** - What the agent can do
- **Safety Attestations** - Proof of safety test compliance
- **Validity Period** - When the certificate expires

### Using Certificates for Agent Collaboration
Once you have an active certificate, you can:
1. **Copy the Certificate ID** - Click the copy button in the certificate details
2. **Share with other agents** - Use the ID in TACP protocol handshakes
3. **Verify certificates** - Other agents can verify your certificate via the public API

### Certificate Lifecycle
- **Active** - Certificate is valid and can be used
- **Expired** - Certificate has passed its expiry date
- **Revoked** - Certificate was manually invalidated

---

## Examples

### Python SDK Example

```python
import httpx

BASE_URL = "http://localhost:8000/v1"
TOKEN = "your-api-token"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

# Create agent
agent = httpx.post(f"{BASE_URL}/agents", headers=HEADERS, json={
    "name": "My Agent",
    "description": "Test agent",
    "framework": "langsmith"
}).json()

# Run evaluation
evaluation = httpx.post(f"{BASE_URL}/evaluations", headers=HEADERS, json={
    "agent_id": agent["id"],
    "suites": ["capability", "safety"]
}).json()

# Poll for results
import time
while True:
    result = httpx.get(f"{BASE_URL}/evaluations/{evaluation['id']}", headers=HEADERS).json()
    if result["status"] == "completed":
        print(f"Score: {result['results']['overall_score']}")
        print(f"Grade: {result['results']['grade']}")
        break
    time.sleep(5)

# Issue certificate
cert = httpx.post(f"{BASE_URL}/certificates", headers=HEADERS, json={
    "agent_id": agent["id"],
    "evaluation_id": evaluation["id"],
    "validity_days": 90
}).json()

print(f"Certificate ID: {cert['id']}")
```

### JavaScript/TypeScript Example

```typescript
const BASE_URL = "http://localhost:8000/v1";
const TOKEN = "your-api-token";

// Fetch traces from LangGraph (via frontend API)
const traces = await fetch("http://localhost:3000/api/fetch-traces", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    url: "https://your-agent.us.langgraph.app",
    apiKey: "lsv2_pt_xxx",
    limit: 20
  })
}).then(r => r.json());

console.log(`Found ${traces.total} traces`);
traces.traces.forEach(trace => {
  console.log(`Thread ${trace.id}: ${trace.messages.length} messages`);
});

// Run evaluation via backend API
const evaluation = await fetch(`${BASE_URL}/evaluations`, {
  method: "POST",
  headers: {
    "Authorization": `Bearer ${TOKEN}`,
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    agent_id: "your-agent-uuid",
    suites: ["capability", "safety", "reliability"]
  })
}).then(r => r.json());

console.log(`Evaluation started: ${evaluation.id}`);
```

### cURL Examples

```bash
# Test agent connectivity
curl -X POST http://localhost:3000/api/test-agent \
  -H "Content-Type: application/json" \
  -d '{"url": "https://your-agent.us.langgraph.app", "apiKey": "lsv2_pt_xxx"}'

# Fetch traces
curl -X POST http://localhost:3000/api/fetch-traces \
  -H "Content-Type: application/json" \
  -d '{"url": "https://your-agent.us.langgraph.app", "apiKey": "lsv2_pt_xxx", "limit": 10}'

# Create agent (backend)
curl -X POST http://localhost:8000/v1/agents \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Agent", "description": "A test agent", "framework": "langsmith"}'

# Run evaluation
curl -X POST http://localhost:8000/v1/evaluations \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "uuid", "suites": ["capability", "safety"]}'

# Verify certificate (public)
curl http://localhost:8000/v1/certificates/cert-uuid/verify

# Search registry (public)
curl "http://localhost:8000/v1/registry/search?min_grade=B&capabilities=calendar"
```

---

## Error Responses

All endpoints return consistent error format:

```json
{
  "detail": "Error message here",
  "code": "ERROR_CODE",
  "status_code": 400
}
```

Common status codes:
- `400` - Bad request (validation error)
- `401` - Unauthorized (missing/invalid token)
- `403` - Forbidden (insufficient permissions)
- `404` - Not found
- `409` - Conflict (duplicate resource)
- `422` - Unprocessable entity (invalid data)
- `500` - Internal server error

---

## Rate Limits

| Endpoint Type | Limit |
|--------------|-------|
| Standard API | 100 req/min |
| Evaluation | 10 req/min |
| Certificate | 20 req/min |
| WebSocket | 5 connections |

---

## Environment Variables

### Frontend (.env.local)
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Backend (.env)
```bash
DATABASE_URL=postgresql://user:pass@localhost:5432/trustmodel
SECRET_KEY=your-secret-key
OPENROUTER_API_KEY=sk-or-v1-xxx  # For LLM-as-Judge
```

---

## Quick Reference

| Action | Method | Endpoint |
|--------|--------|----------|
| Create agent | POST | `/v1/agents` |
| List agents | GET | `/v1/agents` |
| Get agent | GET | `/v1/agents/{id}` |
| Delete agent | DELETE | `/v1/agents/{id}` |
| Fetch LangGraph traces | POST | `/api/fetch-traces` |
| Ingest trace | POST | `/v1/traces/ingest` |
| List traces | GET | `/v1/traces` |
| Get trace | GET | `/v1/traces/{id}` |
| Start evaluation | POST | `/v1/evaluations` |
| Get evaluation | GET | `/v1/evaluations/{id}` |
| Issue certificate | POST | `/v1/certificates` |
| Verify certificate | GET | `/v1/certificates/{id}/verify` |
| Search registry | GET | `/v1/registry/search` |
| Create session | POST | `/v1/sessions` |
| Dashboard stats | GET | `/v1/stats/dashboard` |
