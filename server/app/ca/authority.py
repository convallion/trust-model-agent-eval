"""Certificate Authority management."""

import base64
import json
import os
from pathlib import Path
from typing import Optional, Tuple

import structlog
from nacl.encoding import Base64Encoder
from nacl.signing import SigningKey, VerifyKey

from app.config import settings

logger = structlog.get_logger()


class CertificateAuthority:
    """
    Root Certificate Authority for TrustModel.

    Manages Ed25519 key pairs for signing trust certificates.
    """

    _instance: Optional["CertificateAuthority"] = None
    _signing_key: Optional[SigningKey] = None
    _verify_key: Optional[VerifyKey] = None

    def __new__(cls) -> "CertificateAuthority":
        """Singleton pattern for CA instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize the Certificate Authority."""
        if self._signing_key is None:
            self._load_or_create_keys()

    def _load_or_create_keys(self) -> None:
        """Load existing keys or create new ones."""
        keys_dir = Path(settings.ca_keys_dir)
        keys_dir.mkdir(parents=True, exist_ok=True)

        private_key_path = keys_dir / "root_ca_private.key"
        public_key_path = keys_dir / "root_ca_public.key"

        if settings.root_ca_private_key:
            # Load from environment variable
            logger.info("Loading Root CA key from environment")
            private_key_bytes = base64.b64decode(settings.root_ca_private_key)
            self._signing_key = SigningKey(private_key_bytes)
            self._verify_key = self._signing_key.verify_key
        elif private_key_path.exists():
            # Load from file
            logger.info("Loading Root CA key from file", path=str(private_key_path))
            with open(private_key_path, "rb") as f:
                private_key_bytes = base64.b64decode(f.read())
            self._signing_key = SigningKey(private_key_bytes)
            self._verify_key = self._signing_key.verify_key
        else:
            # Generate new keys
            logger.info("Generating new Root CA key pair")
            self._signing_key = SigningKey.generate()
            self._verify_key = self._signing_key.verify_key

            # Save keys to files
            with open(private_key_path, "wb") as f:
                f.write(
                    base64.b64encode(bytes(self._signing_key))
                )
            with open(public_key_path, "wb") as f:
                f.write(
                    base64.b64encode(bytes(self._verify_key))
                )

            # Set restrictive permissions
            os.chmod(private_key_path, 0o600)
            os.chmod(public_key_path, 0o644)

            logger.info(
                "Root CA key pair generated and saved",
                private_key_path=str(private_key_path),
                public_key_path=str(public_key_path),
            )

    @property
    def signing_key(self) -> SigningKey:
        """Get the signing key."""
        if self._signing_key is None:
            raise RuntimeError("CA not initialized")
        return self._signing_key

    @property
    def verify_key(self) -> VerifyKey:
        """Get the verify key."""
        if self._verify_key is None:
            raise RuntimeError("CA not initialized")
        return self._verify_key

    @property
    def public_key_b64(self) -> str:
        """Get the public key as base64."""
        return base64.b64encode(bytes(self.verify_key)).decode()

    def sign(self, data: bytes) -> str:
        """
        Sign data with the CA private key.

        Args:
            data: Raw bytes to sign

        Returns:
            Base64-encoded signature
        """
        signed = self.signing_key.sign(data)
        # signed.signature contains just the signature without the message
        return base64.b64encode(signed.signature).decode()

    def verify(self, data: bytes, signature: str) -> bool:
        """
        Verify a signature against data.

        Args:
            data: Original data that was signed
            signature: Base64-encoded signature

        Returns:
            True if signature is valid
        """
        try:
            signature_bytes = base64.b64decode(signature)
            self.verify_key.verify(data, signature_bytes)
            return True
        except Exception as e:
            logger.warning("Signature verification failed", error=str(e))
            return False

    @classmethod
    def initialize(cls) -> "CertificateAuthority":
        """Initialize the Certificate Authority (for CLI usage)."""
        return cls()

    @classmethod
    def get_instance(cls) -> "CertificateAuthority":
        """Get the singleton CA instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance


# Global CA instance
ca = CertificateAuthority()
