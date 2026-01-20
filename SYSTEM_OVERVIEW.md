# TrustModel Agent Eval - System Overview

## The Problem

As AI agents become more autonomous and are deployed in production environments, a critical question emerges: **How do you know if an AI agent is trustworthy?**

- Can it complete tasks reliably?
- Will it refuse harmful requests?
- Is it safe to let it collaborate with other agents?
- How do you prove trust to third parties?

## The Solution

**TrustModel Agent Eval** is a comprehensive platform for evaluating, certifying, and enabling secure collaboration between AI agents.

```
┌─────────────────────────────────────────────────────────────────┐
│                    TrustModel Architecture                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌──────────┐    ┌──────────────┐    ┌───────────────┐        │
│   │  Agents  │───▶│  Evaluation  │───▶│  Certificate  │        │
│   │          │    │    Engine    │    │   Issuance    │        │
│   └──────────┘    └──────────────┘    └───────────────┘        │
│        │                                      │                  │
│        │         ┌──────────────┐             │                  │
│        └────────▶│    TACP      │◀────────────┘                  │
│                  │  Protocol    │                                │
│                  │ (Agent-to-   │                                │
│                  │  Agent)      │                                │
│                  └──────────────┘                                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. Agent Registry
Register and manage AI agents from any framework (LangGraph, custom, etc.)

### 2. Evaluation Engine
Run standardized tests across four dimensions:

| Dimension | What It Tests |
|-----------|---------------|
| **Capability** | Task completion, reasoning, tool usage |
| **Safety** | Jailbreak resistance, harmful content refusal |
| **Reliability** | Consistency, error handling, performance |
| **Communication** | Protocol compliance, message formatting |

### 3. Trust Certificates
Digital certificates that prove an agent's evaluation results:
- Cryptographically signed (Ed25519)
- Time-limited validity (90 days)
- Grade-based (A, B, C, D, F)
- Lists certified capabilities
- Publicly verifiable

### 4. TACP Protocol
**Trust Agent Communication Protocol** - enables secure agent-to-agent collaboration.

---

## How It Works

### Via Frontend (Playground UI)

```
1. Register Agent     →  Connect your LangGraph agent or configure API proxy
2. View Traces        →  See all agent conversations and tool calls
3. Run Evaluation     →  Select test suites and start evaluation
4. Review Results     →  View scores, grades, and detailed breakdowns
5. Issue Certificate  →  Generate trust certificate (if eligible)
6. Collaborate        →  Share certificate ID with other agents
```

**Certificate Eligibility Requirements:**
- Overall score ≥ 70%
- Safety score ≥ 85%

### Programmatically (SDK & API)

**Python SDK:**
```python
from trustmodel import TrustModelClient

# Initialize client
client = TrustModelClient(api_key="your-api-key")

# Register an agent
agent = client.agents.create(
    name="my-agent",
    framework="langgraph",
    metadata={"langsmith_api_url": "https://..."}
)

# Run evaluation
evaluation = client.evaluations.create(
    agent_id=agent.id,
    suites=["capability", "safety", "reliability"]
)

# Issue certificate (if eligible)
certificate = client.certificates.create(
    agent_id=agent.id,
    evaluation_id=evaluation.id
)
```

**REST API:**
```bash
# Register agent
curl -X POST https://api.trustmodel.dev/v1/agents \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name": "my-agent", "framework": "langgraph"}'

# Start evaluation
curl -X POST https://api.trustmodel.dev/v1/evaluations \
  -d '{"agent_id": "...", "suites": ["capability", "safety"]}'

# Issue certificate
curl -X POST https://api.trustmodel.dev/v1/certificates \
  -d '{"agent_id": "...", "evaluation_id": "..."}'
```

---

## TACP Protocol (Agent-to-Agent Communication)

TACP enables trusted agents to collaborate securely.

### Handshake Flow

```
Agent A                          Server                          Agent B
   │                               │                                │
   │── Create Session ────────────▶│                                │
   │                               │◀──────────── Accept ───────────│
   │                               │                                │
   │── Trust Challenge (nonce) ───▶│────────────────────────────────▶│
   │                               │                                │
   │                               │◀─── Trust Proof (signed) ──────│
   │◀── Trust Verified ────────────│                                │
   │                               │                                │
   │── Task Request ──────────────▶│────────────────────────────────▶│
   │                               │                                │
   │◀── Progress Updates ──────────│◀───────────────────────────────│
   │◀── Task Complete ─────────────│◀───────────────────────────────│
```

### Key Features

- **Cryptographic Trust**: Ed25519 signatures verify identity
- **Certificate-Based**: Only certified agents can participate
- **Capability Exchange**: Agents declare what they can do
- **Task Delegation**: Agents can request work from each other
- **Audit Trail**: All interactions are logged

### SDK Usage

```python
from trustmodel.protocol import TACPClient

async with TACPClient(api_key="...") as client:
    # Connect to another agent
    session = await client.connect(
        to_agent="other-agent-name",
        purpose="Data analysis collaboration",
        minimum_grade="B"
    )

    # Verify trust
    await session.verify_trust(required_capabilities=["data_analysis"])

    # Delegate a task
    result = await session.request_task(
        task_type="analyze_data",
        description="Analyze Q4 sales data",
        parameters={"dataset": "sales_q4.csv"}
    )
```

---

## Architecture

### Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 14, React, TailwindCSS, React Query |
| Backend | FastAPI, SQLAlchemy, PostgreSQL |
| Protocol | WebSocket, Ed25519 Signatures |
| SDK | Python (async), TypeScript (planned) |

### Key Endpoints

```
Authentication:
  POST /auth/register          - Create account
  POST /auth/login             - Get JWT token

Agents:
  GET  /v1/agents              - List agents
  POST /v1/agents              - Register agent
  GET  /v1/agents/{id}         - Get agent details

Evaluations:
  GET  /v1/evaluations         - List evaluations
  POST /v1/evaluations         - Start evaluation
  GET  /v1/evaluations/{id}    - Get results

Certificates:
  GET  /v1/certificates        - List certificates
  POST /v1/certificates        - Issue certificate
  GET  /v1/certificates/{id}/verify  - Verify certificate

Sessions (TACP):
  POST /v1/sessions            - Create session
  WS   /v1/sessions/{id}/ws    - WebSocket connection
```

---

## Evaluation Scoring

### Score Calculation

Each test suite produces a score (0-100):

```
Overall Score = weighted_average(
    capability_score × 0.3,
    safety_score × 0.3,
    reliability_score × 0.25,
    communication_score × 0.15
)
```

### Grade Mapping

| Grade | Score Range | Certificate Eligible |
|-------|-------------|---------------------|
| A | 90-100 | Yes (if safety ≥ 85) |
| B | 80-89 | Yes (if safety ≥ 85) |
| C | 70-79 | Yes (if safety ≥ 85) |
| D | 60-69 | No |
| F | 0-59 | No |

---

## Certificate Structure

```json
{
  "id": "cert_abc123...",
  "version": "1.0",
  "agent_id": "agent_xyz...",
  "agent_name": "my-assistant",
  "grade": "B",
  "overall_score": 0.85,
  "safety_score": 0.92,
  "capability_score": 0.81,
  "certified_capabilities": [
    "task_completion",
    "tool_usage",
    "safe_responses"
  ],
  "issued_at": "2025-01-19T10:00:00Z",
  "expires_at": "2025-04-19T10:00:00Z",
  "signature": "ed25519_signature_hex..."
}
```

---

## What's Built vs Planned

### Implemented
- Agent registration and management
- LangGraph/LangSmith trace integration
- Evaluation engine with 4 test suites
- Trust certificate issuance and verification
- TACP protocol (sessions, trust verification, task delegation)
- Python SDK
- Web UI (Playground)

### In Progress
- LLM-as-Judge grading (Claude Opus via OpenRouter)
- Real task execution (replacing mock evaluations)
- TACP UI integration

### Planned
- Public certificate registry
- Multi-organization support
- TypeScript SDK
- Webhook notifications
- Advanced analytics dashboard

---

## Quick Start

### 1. Start the Backend
```bash
cd server
uvicorn app.main:app --reload --port 8000
```

### 2. Start the Frontend
```bash
cd playground
npm run dev
```

### 3. Register & Evaluate
1. Create account at `http://localhost:3000/login`
2. Add your agent at `/new`
3. Run evaluation from agent detail page
4. Issue certificate if eligible

---

## Summary

**TrustModel Agent Eval** provides:

1. **Standardized Evaluation** - Consistent testing across capability, safety, reliability, and communication
2. **Verifiable Trust** - Cryptographically signed certificates that prove agent quality
3. **Secure Collaboration** - TACP protocol enables certified agents to work together safely
4. **Developer-Friendly** - Full API, SDK, and web UI for integration

The goal: **Make AI agent trust measurable, verifiable, and portable.**
