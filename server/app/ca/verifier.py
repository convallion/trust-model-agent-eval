"""Certificate verification functionality."""

import json
from typing import Any, Dict

import structlog

from app.ca.authority import CertificateAuthority

logger = structlog.get_logger()


class CertificateVerifier:
    """Verifies trust certificate signatures."""

    def __init__(self) -> None:
        """Initialize the verifier with CA instance."""
        self.ca = CertificateAuthority.get_instance()

    async def verify(
        self,
        certificate_data: Dict[str, Any],
        signature: str,
    ) -> bool:
        """
        Verify a certificate signature.

        Args:
            certificate_data: Dictionary containing certificate fields that were signed
            signature: Base64-encoded signature to verify

        Returns:
            True if signature is valid
        """
        # Serialize to canonical JSON (must match signing process)
        canonical_json = json.dumps(
            certificate_data,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )

        # Verify the signature
        is_valid = self.ca.verify(canonical_json.encode("utf-8"), signature)

        logger.info(
            "Certificate verification",
            certificate_id=certificate_data.get("certificate_id"),
            valid=is_valid,
        )

        return is_valid

    def get_ca_public_key(self) -> str:
        """Get the CA public key for external verification."""
        return self.ca.public_key_b64
