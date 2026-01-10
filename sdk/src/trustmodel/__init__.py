"""
TrustModel SDK - SSL/TLS for AI Agents.

Provides tools for agent instrumentation, evaluation, certification,
and secure agent-to-agent communication.
"""

from trustmodel.version import __version__

# Core exports
from trustmodel.core.config import TrustModelConfig, get_config
from trustmodel.core.exceptions import (
    TrustModelError,
    ConfigurationError,
    AuthenticationError,
    CertificateError,
    EvaluationError,
    ProtocolError,
)

# Connect module
from trustmodel.connect import instrument, TracedAgent

# Evaluate module
from trustmodel.evaluate import evaluate

# Certify module
from trustmodel.certify import certificates

# Protocol module
from trustmodel.protocol import connect, TACPSession

__all__ = [
    # Version
    "__version__",
    # Config
    "TrustModelConfig",
    "get_config",
    # Exceptions
    "TrustModelError",
    "ConfigurationError",
    "AuthenticationError",
    "CertificateError",
    "EvaluationError",
    "ProtocolError",
    # Connect
    "instrument",
    "TracedAgent",
    # Evaluate
    "evaluate",
    # Certify
    "certificates",
    # Protocol
    "connect",
    "TACPSession",
]
