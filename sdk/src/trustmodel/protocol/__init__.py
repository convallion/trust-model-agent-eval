"""TACP Protocol module for agent-to-agent communication."""

from trustmodel.protocol.client import connect, TACPClient
from trustmodel.protocol.session import TACPSession
from trustmodel.protocol.signing import (
    AgentSigner,
    get_signer,
    sign_nonce,
    verify_nonce_signature,
    generate_agent_keypair,
    import_agent_key,
    get_agent_public_key,
)

__all__ = [
    "connect",
    "TACPClient",
    "TACPSession",
    # Signing utilities
    "AgentSigner",
    "get_signer",
    "sign_nonce",
    "verify_nonce_signature",
    "generate_agent_keypair",
    "import_agent_key",
    "get_agent_public_key",
]
