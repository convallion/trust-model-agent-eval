"""Certificate issuance functionality."""

import json
from typing import Any, Dict

import structlog

from app.ca.authority import CertificateAuthority

logger = structlog.get_logger()


class CertificateIssuer:
    """Issues and signs trust certificates."""

    def __init__(self) -> None:
        """Initialize the issuer with CA instance."""
        self.ca = CertificateAuthority.get_instance()

    async def sign(self, certificate_data: Dict[str, Any]) -> str:
        """
        Sign certificate data.

        Args:
            certificate_data: Dictionary containing certificate fields to sign

        Returns:
            Base64-encoded signature
        """
        # Serialize to canonical JSON (sorted keys, no extra whitespace)
        canonical_json = json.dumps(
            certificate_data,
            sort_keys=True,
            separators=(",", ":"),
            default=str,  # Handle datetime, UUID, etc.
        )

        # Sign the canonical JSON bytes
        signature = self.ca.sign(canonical_json.encode("utf-8"))

        logger.info(
            "Certificate signed",
            certificate_id=certificate_data.get("certificate_id"),
            agent_id=certificate_data.get("agent_id"),
        )

        return signature

    def get_issuer_public_key(self) -> str:
        """Get the public key of the issuer for verification."""
        return self.ca.public_key_b64
