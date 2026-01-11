# TrustModel SDK

Python SDK for TrustModel Agent Eval - Enterprise trust infrastructure for AI agents.

## Installation

```bash
pip install trustmodel
```

## Quick Start

```python
from trustmodel import instrument, evaluate, certificates

# 1. Instrument your agent
handle = instrument(agent_name="my-agent")

# 2. Run evaluation
results = await evaluate(agent="my-agent", suites=["capability", "safety"])

# 3. Issue certificate
cert = await certificates.issue(agent="my-agent", evaluation_id=results.id)
```

## Features

- **Instrumentation**: One-line tracing for AI agents
- **Evaluation**: Comprehensive evaluation suites
- **Certificates**: Ed25519-signed trust certificates
- **TACP Protocol**: Agent-to-agent communication

## Documentation

See the main project README for full documentation.
