"""Pydantic schemas for API request/response validation."""

from app.schemas.agent import (
    AgentCreate,
    AgentResponse,
    AgentUpdate,
)
from app.schemas.auth import (
    APIKeyCreate,
    APIKeyResponse,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.schemas.certificate import (
    CertificateIssueRequest,
    CertificateResponse,
    CertificateRevokeRequest,
    CertificateVerifyResponse,
)
from app.schemas.evaluation import (
    EvaluationRequest,
    EvaluationResponse,
    EvaluationStatus,
)
from app.schemas.session import (
    SessionCreate,
    SessionResponse,
)
from app.schemas.trace import (
    SpanCreate,
    TraceCreate,
    TraceResponse,
)

__all__ = [
    # Auth
    "RegisterRequest",
    "LoginRequest",
    "TokenResponse",
    "UserResponse",
    "APIKeyCreate",
    "APIKeyResponse",
    # Agent
    "AgentCreate",
    "AgentUpdate",
    "AgentResponse",
    # Trace
    "TraceCreate",
    "SpanCreate",
    "TraceResponse",
    # Evaluation
    "EvaluationRequest",
    "EvaluationResponse",
    "EvaluationStatus",
    # Certificate
    "CertificateIssueRequest",
    "CertificateResponse",
    "CertificateVerifyResponse",
    "CertificateRevokeRequest",
    # Session
    "SessionCreate",
    "SessionResponse",
]
