# TrustModel Agent Eval

**SSL/TLS for AI Agents** - Enterprise trust infrastructure for evaluating, certifying, and enabling secure communication between AI agents.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     TRUSTMODEL AGENT EVAL SYSTEM                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌───────────────────┐  ┌───────────────────┐  ┌───────────────────┐   │
│  │                   │  │                   │  │                   │   │
│  │    1. CONNECT     │  │    2. EVALUATE    │  │    3. CERTIFY     │   │
│  │                   │  │                   │  │                   │   │
│  │  Plug any agent   │  │  Comprehensive    │  │  Issue trust      │   │
│  │  in 5 minutes     │  │  eval suite       │  │  certificates     │   │
│  │                   │  │                   │  │                   │   │
│  └───────────────────┘  └───────────────────┘  └───────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Start the Platform

```bash
# Clone and setup
git clone <repository>
cd trust-model-agent-eval
cp .env.example .env

# Start all services
docker-compose up -d

# Run database migrations
make migrate
```

### 2. Install the SDK

```bash
pip install trustmodel
```

### 3. Connect Your Agent

```python
from trustmodel import instrument

# One line to instrument any agent
instrument(
    agent_name="my-agent",
    api_key="tm_...",
)

# That's it. Run your agent normally.
# All traces flow to TrustModel.
```

### 4. Run Evaluation

```python
from trustmodel import evaluate

results = await evaluate(
    agent="my-agent",
    suites=["capability", "safety", "reliability", "communication"],
)

print(f"Overall Score: {results.overall_score}")
print(f"Grade: {results.grade}")
print(f"Certificate Eligible: {results.certificate_eligible}")
```

### 5. Get Your Trust Certificate

```python
from trustmodel import certificates

cert = await certificates.issue(agent="my-agent", evaluation_id=results.id)
print(f"Certificate ID: {cert.certificate_id}")
print(f"Expires: {cert.expires_at}")
```

## Architecture

```
trust-model-agent-eval/
├── server/          # FastAPI backend + Evaluation Engine + Certificate Authority
├── sdk/             # Python SDK for agent instrumentation
├── frontend/        # React/Next.js Playground UI
├── tests/           # Integration tests
└── examples/        # Usage examples
```

## Components

### Backend Server
- **FastAPI** REST API with async support
- **PostgreSQL** for persistent storage
- **Redis** for caching and job queues
- **Celery** for background evaluation tasks
- **Ed25519 Certificate Authority** for trust certificates

### Evaluation Engine
- **Capability Suite**: Task completion, tool proficiency, reasoning quality
- **Safety Suite**: Jailbreak resistance, boundary adherence, data protection
- **Reliability Suite**: Consistency, graceful degradation, idempotency
- **Communication Suite**: Protocol compliance, trust verification

### Python SDK
- One-line instrumentation with auto-detection
- OpenTelemetry-based tracing
- Proxy mode for unmodifiable agents
- TACP protocol client for agent-to-agent communication

### Playground UI
- Real-time trace viewer
- Evaluation dashboard
- Certificate management
- Trust registry browser

## API Endpoints

```
POST   /auth/register              # Register organization
POST   /auth/login                 # Get JWT token

POST   /v1/agents                  # Register agent
GET    /v1/agents                  # List agents
GET    /v1/agents/{id}             # Get agent details

POST   /v1/traces                  # Ingest traces
GET    /v1/traces/{id}             # Get trace with spans

POST   /v1/evaluations             # Start evaluation
GET    /v1/evaluations/{id}        # Get results

POST   /v1/certificates            # Issue certificate
GET    /v1/certificates/{id}       # Get certificate
GET    /v1/certificates/{id}/verify # Verify certificate
GET    /v1/registry                # Public trust registry
```

## CLI Commands

```bash
trustmodel agent register --name "my-agent" --type coding
trustmodel agent list
trustmodel proxy start --port 8080
trustmodel evaluate --agent "my-agent" --suites capability,safety
trustmodel cert issue --agent "my-agent" --evaluation <id>
trustmodel cert verify <cert-id>
```

## Development

```bash
# Install dependencies
make install

# Run tests
make test

# Start development server
make server

# Format and lint code
make format
make lint
```

## License

MIT
