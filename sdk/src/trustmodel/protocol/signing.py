"""Cryptographic signing utilities for TACP protocol."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional
from uuid import UUID

from nacl.signing import SigningKey, VerifyKey
from nacl.encoding import HexEncoder
from nacl.exceptions import BadSignatureError

from trustmodel.core.config import get_config
from trustmodel.core.logging import get_logger

logger = get_logger(__name__)


class AgentSigner:
    """
    Handles Ed25519 signing operations for agents.

    Keys are stored locally in the SDK's key directory.
    """

    def __init__(self, keys_dir: Optional[Path] = None) -> None:
        """
        Initialize the signer.

        Args:
            keys_dir: Directory to store keys (defaults to ~/.trustmodel/keys)
        """
        config = get_config()
        self.keys_dir = keys_dir or Path.home() / ".trustmodel" / "keys"
        self.keys_dir.mkdir(parents=True, exist_ok=True)

        # Cache loaded keys
        self._signing_keys: dict[UUID, SigningKey] = {}
        self._verify_keys: dict[UUID, VerifyKey] = {}

    def _get_key_path(self, agent_id: UUID, key_type: str) -> Path:
        """Get path to a key file."""
        return self.keys_dir / f"{agent_id}.{key_type}.key"

    def generate_keypair(self, agent_id: UUID) -> tuple[str, str]:
        """
        Generate a new Ed25519 keypair for an agent.

        Args:
            agent_id: The agent's ID

        Returns:
            Tuple of (public_key_hex, private_key_hex)
        """
        signing_key = SigningKey.generate()
        verify_key = signing_key.verify_key

        # Save keys
        private_path = self._get_key_path(agent_id, "private")
        public_path = self._get_key_path(agent_id, "public")

        private_path.write_bytes(signing_key.encode())
        public_path.write_bytes(verify_key.encode())

        # Secure private key
        os.chmod(private_path, 0o600)

        # Cache
        self._signing_keys[agent_id] = signing_key
        self._verify_keys[agent_id] = verify_key

        logger.info("Generated keypair", agent_id=str(agent_id))

        return (
            verify_key.encode(encoder=HexEncoder).decode(),
            signing_key.encode(encoder=HexEncoder).decode(),
        )

    def load_signing_key(self, agent_id: UUID) -> Optional[SigningKey]:
        """Load an agent's signing key."""
        if agent_id in self._signing_keys:
            return self._signing_keys[agent_id]

        private_path = self._get_key_path(agent_id, "private")
        if not private_path.exists():
            return None

        try:
            key_bytes = private_path.read_bytes()
            signing_key = SigningKey(key_bytes)
            self._signing_keys[agent_id] = signing_key
            return signing_key
        except Exception as e:
            logger.error("Failed to load signing key", error=str(e))
            return None

    def load_verify_key(self, agent_id: UUID) -> Optional[VerifyKey]:
        """Load an agent's verify (public) key."""
        if agent_id in self._verify_keys:
            return self._verify_keys[agent_id]

        public_path = self._get_key_path(agent_id, "public")
        if not public_path.exists():
            return None

        try:
            key_bytes = public_path.read_bytes()
            verify_key = VerifyKey(key_bytes)
            self._verify_keys[agent_id] = verify_key
            return verify_key
        except Exception as e:
            logger.error("Failed to load verify key", error=str(e))
            return None

    def import_signing_key(self, agent_id: UUID, private_key_hex: str) -> None:
        """Import a private key from hex string."""
        signing_key = SigningKey(private_key_hex.encode(), encoder=HexEncoder)
        verify_key = signing_key.verify_key

        # Save
        private_path = self._get_key_path(agent_id, "private")
        public_path = self._get_key_path(agent_id, "public")

        private_path.write_bytes(signing_key.encode())
        public_path.write_bytes(verify_key.encode())
        os.chmod(private_path, 0o600)

        # Cache
        self._signing_keys[agent_id] = signing_key
        self._verify_keys[agent_id] = verify_key

    def sign(self, agent_id: UUID, message: str) -> Optional[str]:
        """
        Sign a message.

        Args:
            agent_id: The agent's ID
            message: Message to sign

        Returns:
            Hex-encoded signature or None if key not found
        """
        signing_key = self.load_signing_key(agent_id)
        if not signing_key:
            return None

        signed = signing_key.sign(message.encode())
        return signed.signature.hex()

    def verify(
        self,
        agent_id: UUID,
        message: str,
        signature_hex: str,
        public_key_hex: Optional[str] = None,
    ) -> bool:
        """
        Verify a signature.

        Args:
            agent_id: The agent's ID
            message: Original message
            signature_hex: Hex-encoded signature
            public_key_hex: Optional public key to use

        Returns:
            True if signature is valid
        """
        try:
            if public_key_hex:
                verify_key = VerifyKey(public_key_hex.encode(), encoder=HexEncoder)
            else:
                verify_key = self.load_verify_key(agent_id)
                if not verify_key:
                    return False

            signature = bytes.fromhex(signature_hex)
            verify_key.verify(message.encode(), signature)
            return True

        except BadSignatureError:
            return False
        except Exception as e:
            logger.error("Verification error", error=str(e))
            return False

    def get_public_key(self, agent_id: UUID) -> Optional[str]:
        """Get public key as hex string."""
        verify_key = self.load_verify_key(agent_id)
        if not verify_key:
            return None
        return verify_key.encode(encoder=HexEncoder).decode()

    def has_keypair(self, agent_id: UUID) -> bool:
        """Check if agent has a keypair."""
        private_path = self._get_key_path(agent_id, "private")
        return private_path.exists()

    def ensure_keypair(self, agent_id: UUID) -> str:
        """Ensure agent has a keypair, generating if needed."""
        if not self.has_keypair(agent_id):
            public_key, _ = self.generate_keypair(agent_id)
            return public_key
        return self.get_public_key(agent_id) or ""


# Global signer instance
_signer: Optional[AgentSigner] = None


def get_signer() -> AgentSigner:
    """Get the global signer instance."""
    global _signer
    if _signer is None:
        _signer = AgentSigner()
    return _signer


# Convenience async functions
async def sign_nonce(agent_id: UUID, nonce: str) -> str:
    """
    Sign a nonce for trust verification.

    Args:
        agent_id: The agent's ID
        nonce: The nonce to sign

    Returns:
        Hex-encoded signature

    Raises:
        ValueError: If no key found for agent
    """
    signer = get_signer()

    # Ensure agent has a keypair
    if not signer.has_keypair(agent_id):
        # Generate one if not exists
        signer.generate_keypair(agent_id)

    signature = signer.sign(agent_id, nonce)
    if signature is None:
        raise ValueError(f"Failed to sign nonce for agent {agent_id}")

    return signature


async def verify_nonce_signature(
    agent_id: UUID,
    nonce: str,
    signature: str,
    public_key: Optional[str] = None,
) -> bool:
    """
    Verify a nonce signature.

    Args:
        agent_id: The agent's ID
        nonce: The original nonce
        signature: The signature to verify
        public_key: Optional public key to use

    Returns:
        True if signature is valid
    """
    return get_signer().verify(agent_id, nonce, signature, public_key)


async def generate_agent_keypair(agent_id: UUID) -> tuple[str, str]:
    """Generate a keypair for an agent."""
    return get_signer().generate_keypair(agent_id)


async def import_agent_key(agent_id: UUID, private_key_hex: str) -> None:
    """Import a private key for an agent."""
    get_signer().import_signing_key(agent_id, private_key_hex)


async def get_agent_public_key(agent_id: UUID) -> Optional[str]:
    """Get an agent's public key."""
    return get_signer().get_public_key(agent_id)
