# TrustModel Agent Eval System

## Complete Technical Documentation

**Version:** 0.1.0
**Last Updated:** January 2025
**Status:** MVP / Development

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Architecture](#system-architecture)
3. [Technology Stack](#technology-stack)
4. [Component Deep Dive](#component-deep-dive)
5. [API Reference](#api-reference)
6. [Database Schema](#database-schema)
7. [What Works](#what-works)
8. [What Doesn't Work](#what-doesnt-work)
9. [What Needs to Be Built](#what-needs-to-be-built)
10. [Deployment Guide](#deployment-guide)

---

## Executive Summary

TrustModel is an **enterprise trust infrastructure for AI agents** - essentially "SSL/TLS for AI Agents". It provides:

- **Tracing**: Capture all LLM API calls made by agents
- **Evaluation**: Test agents across capability, safety, reliability, and communication dimensions
- **Certification**: Issue cryptographically signed trust certificates
- **Registry**: Public registry of certified agents
- **TACP Protocol**: Agent-to-agent communication with trust verification

### Core Value Proposition

Just as SSL certificates tell users "this website is trustworthy", TrustModel certificates tell systems "this AI agent has been evaluated and meets trust standards".

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND (Next.js)                              │
│                           http://localhost:3000                              │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐            │
│  │  Dashboard  │ │   Agents    │ │ Evaluations │ │Certificates │            │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘            │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │ HTTP/WebSocket
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            BACKEND API (FastAPI)                             │
│                           http://localhost:8000                              │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐            │
│  │    Auth     │ │   Agents    │ │   Traces    │ │    Evals    │            │
│  │  /auth/*    │ │ /v1/agents  │ │ /v1/traces  │ │/v1/evaluate │            │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘            │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐            │
│  │   Certs     │ │  Sessions   │ │   Stats     │ │  Registry   │            │
│  │/v1/certs    │ │/v1/sessions │ │ /v1/stats   │ │/v1/registry │            │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘            │
└───────┬─────────────────┬─────────────────┬─────────────────┬───────────────┘
        │                 │                 │                 │
        ▼                 ▼                 ▼                 ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│  PostgreSQL   │ │     Redis     │ │Celery Workers │ │      CA       │
│   Database    │ │  Cache/Queue  │ │  Background   │ │ Certificate   │
│               │ │               │ │    Tasks      │ │  Authority    │
└───────────────┘ └───────────────┘ └───────────────┘ └───────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                              SDK / CLI                                       │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐            │
│  │ instrument()│ │   Proxy     │ │  evaluate() │ │certificates │            │
│  │  Auto-trace │ │ LLM Capture │ │  Trigger    │ │   Manage    │            │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘            │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Agent Registration**: User registers agent via frontend → Stored in PostgreSQL
2. **Trace Capture**: SDK/Proxy intercepts LLM calls → Sends to `/v1/traces` → Stored in DB
3. **Evaluation**: User triggers eval → Celery worker runs tests → Results stored
4. **Certification**: If passed, CA signs certificate → Certificate stored with Ed25519 signature
5. **Verification**: Any system can verify certificate via `/v1/certificates/{id}/verify`

---

## Technology Stack

### Backend (`/server`)

| Component | Technology | Purpose |
|-----------|------------|---------|
| Framework | FastAPI 0.109+ | Async REST API |
| Database | PostgreSQL 16 | Primary data store |
| ORM | SQLAlchemy 2.0 (async) | Database abstraction |
| Migrations | Alembic | Schema versioning |
| Cache/Queue | Redis 7 | Caching + Celery broker |
| Background Jobs | Celery | Async task processing |
| Auth | python-jose (JWT) | Token-based auth |
| Crypto | PyNaCl (Ed25519) | Certificate signing |
| Validation | Pydantic v2 | Schema validation |

### Frontend (`/playground`)

| Component | Technology | Purpose |
|-----------|------------|---------|
| Framework | Next.js 14 | React framework |
| Language | TypeScript | Type safety |
| Styling | Tailwind CSS | Utility-first CSS |
| State | React Query | Server state management |
| HTTP Client | Axios | API calls |
| Charts | Recharts | Data visualization |
| Icons | Heroicons | UI icons |

### SDK (`/sdk`)

| Component | Technology | Purpose |
|-----------|------------|---------|
| Language | Python 3.10+ | SDK language |
| HTTP | httpx | Async HTTP client |
| CLI | Click + Rich | Command-line interface |
| Tracing | OpenTelemetry | Span/trace capture |
| Proxy | aiohttp | LLM proxy server |

### Infrastructure

| Component | Technology | Purpose |
|-----------|------------|---------|
| Containers | Docker Compose | Local development |
| API Gateway | Uvicorn | ASGI server |
| Process Manager | Celery | Worker processes |

---

## Component Deep Dive

### 1. Backend Server (`/server/app`)

#### Directory Structure

```
server/app/
├── main.py                 # FastAPI app initialization
├── config.py               # Settings (pydantic-settings)
├── api/
│   ├── deps.py             # Dependency injection (get_db, get_current_user)
│   ├── auth.py             # Login, register, API keys
│   └── v1/
│       ├── router.py       # Main API router
│       ├── agents.py       # Agent CRUD
│       ├── traces.py       # Trace queries
│       ├── trace_ingest.py # Trace ingestion endpoint
│       ├── evaluations.py  # Evaluation management
│       ├── certificates.py # Certificate lifecycle
│       ├── sessions.py     # TACP sessions
│       ├── stats.py        # Dashboard statistics
│       └── registry.py     # Public trust registry
├── core/
│   ├── security.py         # JWT, password hashing
│   ├── database.py         # Async SQLAlchemy setup
│   └── redis.py            # Redis connection
├── models/                 # SQLAlchemy ORM models
│   ├── user.py             # User, Organization, APIKey
│   ├── agent.py            # Agent registration
│   ├── trace.py            # Trace, Span
│   ├── evaluation.py       # EvaluationRun
│   ├── certificate.py      # Certificate, Revocation
│   └── session.py          # TACP Sessions, Messages
├── schemas/                # Pydantic request/response schemas
├── services/               # Business logic layer
│   ├── agent_service.py
│   ├── trace_service.py
│   ├── evaluation_service.py
│   ├── certificate_service.py
│   └── session_service.py
├── ca/                     # Certificate Authority
│   ├── authority.py        # Root CA key management
│   ├── issuer.py           # Certificate issuance
│   └── verifier.py         # Signature verification
├── evaluation/             # Evaluation Engine
│   ├── engine.py           # Orchestrator
│   ├── executor.py         # Parallel task runner
│   └── suites/
│       ├── capability.py   # Task completion tests
│       ├── safety.py       # Harmful output tests
│       ├── reliability.py  # Consistency tests
│       └── communication.py # Protocol tests
└── workers/                # Celery background tasks
    ├── celery_app.py       # Celery configuration
    ├── evaluation_tasks.py # Background eval runner
    └── trace_tasks.py      # Trace aggregation
```

#### Key Files Explained

**`main.py`** - FastAPI application entry point
```python
app = FastAPI(title="TrustModel API")
app.include_router(auth_router)
app.include_router(v1_router, prefix="/v1")
```

**`api/deps.py`** - Dependency injection for all routes
```python
async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    # Validates JWT and returns user

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    # Yields database session
```

**`services/trace_service.py`** - Trace ingestion logic
```python
class TraceService:
    async def ingest_batch(self, batch: TraceBatchCreate) -> TraceBatchResult:
        # Validates traces, stores in DB, broadcasts to WebSocket
```

**`ca/authority.py`** - Certificate Authority
```python
class CertificateAuthority:
    def __init__(self):
        self.signing_key = nacl.signing.SigningKey.generate()

    def sign(self, data: bytes) -> str:
        # Returns Ed25519 signature
```

### 2. Frontend (`/playground/src`)

#### Directory Structure

```
playground/src/
├── app/                    # Next.js App Router
│   ├── layout.tsx          # Root layout with providers
│   ├── page.tsx            # Dashboard home
│   ├── login/page.tsx      # Login/register
│   ├── agents/
│   │   ├── page.tsx        # Agent list
│   │   └── [id]/page.tsx   # Agent detail with tabs
│   ├── evaluations/
│   │   ├── page.tsx        # Evaluation list
│   │   └── [id]/page.tsx   # Evaluation results
│   ├── certificates/
│   │   ├── page.tsx        # Certificate list
│   │   └── [id]/page.tsx   # Certificate detail
│   ├── traces/page.tsx     # Trace viewer
│   └── observability/page.tsx # Metrics dashboard
├── components/
│   ├── layout/
│   │   ├── DashboardLayout.tsx  # Main layout wrapper
│   │   └── Sidebar.tsx          # Navigation sidebar
│   ├── ui/
│   │   ├── GradeBadge.tsx       # A/B/C/D/F badge
│   │   └── StatusBadge.tsx      # Status indicator
│   └── dashboard/
│       ├── StatsCards.tsx       # Metric cards
│       └── TrustScoreChart.tsx  # Score visualization
└── lib/
    └── api.ts              # API client with all endpoints
```

#### Key Pages Explained

**`agents/[id]/page.tsx`** - Agent detail with 4 tabs:
- **Overview**: Stats, recent evaluations
- **Setup**: Framework-specific integration code (Anthropic, OpenAI, Claude Code, etc.)
- **Traces**: List of captured API calls
- **Evaluations**: Run and view evaluations

**`evaluations/[id]/page.tsx`** - Evaluation results:
- Visual score bars with color coding
- Real-time polling while running
- Grade card (A/B/C/D/F)
- Issue certificate button

**`lib/api.ts`** - Centralized API client:
```typescript
export const api = {
  login: async (email, password) => {...},
  getAgents: async () => {...},
  startEvaluation: async (agentId, suites) => {...},
  issueCertificate: async (agentId, evaluationId) => {...},
  // ... all endpoints
}
```

### 3. SDK (`/sdk/src/trustmodel`)

#### Directory Structure

```
sdk/src/trustmodel/
├── __init__.py             # Public exports: instrument, evaluate, certificates
├── version.py              # Version string
├── core/
│   ├── config.py           # SDK configuration
│   ├── exceptions.py       # Custom exceptions
│   └── logging.py          # Structured logging
├── models/                 # Pydantic models
├── connect/
│   ├── instrument.py       # instrument() function
│   ├── tracer.py           # Trace capture
│   └── auto/
│       ├── anthropic.py    # Anthropic auto-patch
│       ├── openai.py       # OpenAI auto-patch
│       └── langchain.py    # LangChain auto-patch
├── api/
│   └── client.py           # HTTP client to server
└── cli/
    ├── main.py             # CLI entry point
    └── commands/
        ├── agent.py        # trustmodel agent ...
        ├── proxy.py        # trustmodel proxy start
        ├── evaluate.py     # trustmodel evaluate
        └── cert.py         # trustmodel cert ...
```

#### Key Components

**`cli/commands/proxy.py`** - LLM Proxy:
```python
# Intercepts LLM API calls, forwards to real API, captures traces
async def anthropic_handler(request):
    # 1. Read request
    # 2. Forward to api.anthropic.com
    # 3. Capture trace (model, tokens, latency)
    # 4. Send trace to TrustModel server
    # 5. Return response to client
```

---

## API Reference

### Authentication

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/auth/register` | POST | Register new user + organization |
| `/auth/login` | POST | Get JWT token |
| `/auth/me` | GET | Get current user profile |
| `/auth/api-keys` | POST | Create API key |

### Agents

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/agents` | GET | List agents (paginated) |
| `/v1/agents` | POST | Register new agent |
| `/v1/agents/{id}` | GET | Get agent details |
| `/v1/agents/{id}` | DELETE | Deregister agent |

### Traces

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/traces` | GET | List traces (filter by agent) |
| `/v1/traces` | POST | Ingest trace batch |
| `/v1/traces/{id}` | GET | Get trace with spans |
| `/v1/traces/stream` | WebSocket | Real-time trace stream |

### Evaluations

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/evaluations` | GET | List evaluations |
| `/v1/evaluations` | POST | Start new evaluation |
| `/v1/evaluations/{id}` | GET | Get evaluation results |

### Certificates

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/certificates` | GET | List certificates |
| `/v1/certificates` | POST | Issue certificate |
| `/v1/certificates/{id}` | GET | Get certificate |
| `/v1/certificates/{id}/verify` | GET | Verify signature |
| `/v1/certificates/{id}/revoke` | POST | Revoke certificate |

### Stats

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/stats/dashboard` | GET | Dashboard summary stats |
| `/v1/stats/observability` | GET | Detailed metrics |

---

## Database Schema

### Core Tables

```sql
-- Users and Organizations
organizations (id, name, created_at)
users (id, email, hashed_password, organization_id, created_at)
api_keys (id, key_hash, user_id, name, scopes, expires_at)

-- Agents
agents (id, name, agent_type, framework, organization_id, status, metadata, created_at)

-- Traces
traces (id, agent_id, session_id, name, started_at, ended_at, metadata)
spans (id, trace_id, parent_span_id, span_type, name, started_at, ended_at, attributes, status)

-- Evaluations
evaluation_runs (id, agent_id, status, suites, config, started_at, completed_at,
                 results, overall_score, capability_score, safety_score,
                 reliability_score, communication_score, grade)

-- Certificates
certificates (id, agent_id, evaluation_id, version, grade, overall_score,
              capability_score, safety_score, reliability_score, communication_score,
              capabilities, not_certified, safety_attestations,
              issued_at, expires_at, status, signature)
revocations (id, certificate_id, reason, revoked_at)

-- TACP Sessions
tacp_sessions (id, initiator_agent_id, responder_agent_id, status, scope, constraints, created_at, ended_at)
session_messages (id, session_id, sender_agent_id, recipient_agent_id, message_type, payload, signature, created_at)
```

---

## What Works

### Fully Functional

| Feature | Status | Notes |
|---------|--------|-------|
| User registration & login | ✅ Working | JWT-based auth with 24h expiry |
| Agent registration | ✅ Working | Create, list, view agents |
| Trace ingestion | ✅ Working | POST traces via API |
| Trace viewing | ✅ Working | List traces in frontend |
| Evaluation triggering | ✅ Working | Start evaluations from UI |
| Certificate issuance | ✅ Working | Issue after passing eval |
| Certificate verification | ✅ Working | Verify signature via API |
| Certificate revocation | ✅ Working | Revoke with reason |
| Dashboard stats | ✅ Working | Counts and metrics |
| SDK CLI | ✅ Working | All commands functional |
| LLM Proxy | ✅ Working | Forwards to Anthropic/OpenAI |

### Partially Functional

| Feature | Status | Notes |
|---------|--------|-------|
| Evaluation engine | ⚠️ Partial | Runs but returns mock scores |
| Auto-instrumentation | ⚠️ Partial | Needs testing with real LLM calls |
| TACP Sessions | ⚠️ Partial | WebSocket connected, needs protocol testing |
| Real-time trace stream | ⚠️ Partial | WebSocket exists, UI not connected |

---

## What Doesn't Work

### Not Implemented

| Feature | Status | What's Missing |
|---------|--------|----------------|
| Real evaluation tests | ❌ Not Done | Actual LLM test prompts, grading logic |
| Model-as-judge grading | ❌ Not Done | Claude/GPT grading responses |
| Capability task bank | ❌ Not Done | YAML files with test tasks |
| Safety prompt injection tests | ❌ Not Done | Adversarial prompts |
| Reliability stress tests | ❌ Not Done | Repeated calls, error injection |
| Communication protocol tests | ❌ Not Done | TACP compliance checking |
| Celery worker execution | ❌ Broken | Workers defined but not running evals |
| SDK auto-patching | ❌ Not Done | Anthropic/OpenAI monkey-patching |
| Trust registry search | ❌ Not Done | Public registry API |
| Agent collaboration | ❌ Not Done | TACP agent-to-agent flow |

### Known Bugs

1. **Token expiry not handled gracefully** - Frontend shows error instead of redirecting
2. **Evaluation results always empty** - Engine returns mock data
3. **Celery workers not processing** - Tasks queued but not executed
4. **Trace metadata missing fields** - Some spans don't capture all attributes

---

## What Needs to Be Built

### Priority 1: Core Evaluation System

#### 1.1 Evaluation Task Banks
Create YAML files with actual test cases:

```yaml
# server/app/evaluation/tasks/capability_tasks.yaml
tasks:
  - id: code_generation_1
    name: "Generate Python function"
    prompt: "Write a Python function that calculates fibonacci numbers"
    expected_behavior:
      - contains_code: true
      - language: python
      - has_function_definition: true
    grading: outcome_check

  - id: tool_use_1
    name: "Use calculator tool"
    prompt: "What is 15% of 847?"
    tools_available: [calculator]
    expected_behavior:
      - tool_called: calculator
      - correct_result: 127.05
    grading: tool_audit
```

#### 1.2 Grading System
Implement graders in `server/app/evaluation/graders/`:

```python
# outcome_grader.py
class OutcomeGrader:
    def grade(self, response: str, expected: dict) -> float:
        score = 0.0
        if expected.get("contains_code") and "def " in response:
            score += 0.5
        # ... more checks
        return score

# model_judge.py
class ModelJudge:
    async def grade(self, prompt: str, response: str, criteria: list) -> float:
        # Use Claude to evaluate response quality
        judgment = await self.client.messages.create(
            model="claude-sonnet-4-20250514",
            messages=[{
                "role": "user",
                "content": f"Rate this response on {criteria}:\n\n{response}"
            }]
        )
        return self.parse_score(judgment)
```

#### 1.3 Evaluation Executor
Fix `server/app/evaluation/engine.py`:

```python
class EvaluationEngine:
    async def run_evaluation(self, agent_id, suites, config):
        results = {}
        for suite in suites:
            suite_runner = self.get_suite(suite)
            tasks = self.load_tasks(suite)
            suite_results = await suite_runner.run(agent_id, tasks)
            results[suite] = suite_results
        return self.aggregate_scores(results)
```

### Priority 2: SDK Auto-Instrumentation

#### 2.1 Anthropic Patching
```python
# sdk/src/trustmodel/connect/auto/anthropic.py
def patch_anthropic():
    original_create = anthropic.Anthropic.messages.create

    @wraps(original_create)
    async def traced_create(self, *args, **kwargs):
        span = tracer.start_span("anthropic.messages.create")
        span.set_attribute("model", kwargs.get("model"))
        try:
            result = await original_create(self, *args, **kwargs)
            span.set_attribute("input_tokens", result.usage.input_tokens)
            span.set_attribute("output_tokens", result.usage.output_tokens)
            return result
        finally:
            span.end()

    anthropic.Anthropic.messages.create = traced_create
```

### Priority 3: TACP Protocol

#### 3.1 Agent-to-Agent Flow
```python
# Complete TACP handshake
async def connect_to_agent(target_agent_id: str, purpose: str):
    # 1. Verify target agent's certificate
    cert = await verify_certificate(target_agent_id)
    if not cert.is_valid():
        raise TrustError("Target agent not trusted")

    # 2. Create session
    session = await create_session(target_agent_id, purpose)

    # 3. Exchange capabilities
    my_capabilities = get_my_capabilities()
    their_capabilities = await session.exchange_capabilities(my_capabilities)

    # 4. Return session for task requests
    return TACPSession(session, their_capabilities)
```

### Priority 4: Production Readiness

#### 4.1 Security Hardening
- [ ] Rate limiting on all endpoints
- [ ] Input sanitization
- [ ] SQL injection prevention audit
- [ ] XSS prevention in frontend
- [ ] CORS configuration
- [ ] API key rotation

#### 4.2 Observability
- [ ] Structured logging (structlog)
- [ ] Metrics export (Prometheus)
- [ ] Distributed tracing (Jaeger)
- [ ] Error tracking (Sentry)
- [ ] Health checks

#### 4.3 Scalability
- [ ] Database connection pooling
- [ ] Redis caching layer
- [ ] Celery worker scaling
- [ ] Load balancer configuration
- [ ] Database read replicas

### Priority 5: Additional Features

#### 5.1 Multi-tenancy
- Organization-based isolation
- Role-based access control (Admin, Developer, Viewer)
- Team management

#### 5.2 Webhooks
- Evaluation completion notifications
- Certificate expiry warnings
- Trust score changes

#### 5.3 Integrations
- GitHub Actions for CI/CD evaluation
- Slack notifications
- PagerDuty alerts

---

## Deployment Guide

### Local Development

```bash
# 1. Start infrastructure
docker-compose up -d db redis

# 2. Run migrations
cd server && alembic upgrade head

# 3. Start backend
uvicorn app.main:app --reload --port 8000

# 4. Start Celery worker (separate terminal)
celery -A app.workers.celery_app worker --loglevel=info

# 5. Start frontend (separate terminal)
cd playground && npm run dev
```

### Docker Compose (Full Stack)

```bash
docker-compose up --build
```

Services:
- API: http://localhost:8000
- Frontend: http://localhost:3000
- PostgreSQL: localhost:5432
- Redis: localhost:6379

### Environment Variables

```bash
# Required
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/trustmodel
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=your-secret-key-here

# Optional
ANTHROPIC_API_KEY=sk-ant-...  # For model-as-judge grading
OPENAI_API_KEY=sk-...         # For OpenAI-based agents
```

---

## Appendix: File Inventory

### Backend Files (45 files)

| Path | Lines | Description |
|------|-------|-------------|
| `server/app/main.py` | 50 | FastAPI app |
| `server/app/config.py` | 40 | Settings |
| `server/app/api/deps.py` | 80 | Dependencies |
| `server/app/api/auth.py` | 120 | Auth endpoints |
| `server/app/api/v1/*.py` | 800 | All v1 routes |
| `server/app/models/*.py` | 400 | ORM models |
| `server/app/schemas/*.py` | 500 | Pydantic schemas |
| `server/app/services/*.py` | 600 | Business logic |
| `server/app/ca/*.py` | 200 | Certificate authority |
| `server/app/evaluation/*.py` | 400 | Eval engine |
| `server/app/workers/*.py` | 250 | Celery tasks |

### Frontend Files (25 files)

| Path | Lines | Description |
|------|-------|-------------|
| `playground/src/app/**/*.tsx` | 2500 | All pages |
| `playground/src/components/**/*.tsx` | 500 | UI components |
| `playground/src/lib/api.ts` | 350 | API client |

### SDK Files (20 files)

| Path | Lines | Description |
|------|-------|-------------|
| `sdk/src/trustmodel/**/*.py` | 1500 | SDK code |
| `sdk/src/trustmodel/cli/**/*.py` | 500 | CLI commands |

---

## Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/my-feature`
3. Make changes and test locally
4. Submit pull request

## License

MIT License - See LICENSE file

---

*Document generated: January 2025*
*TrustModel v0.1.0*
