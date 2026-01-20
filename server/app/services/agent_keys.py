"""Agent key management for TACP protocol signing."""

from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Optional
from uuid import UUID

import structlog
from nacl.signing import SigningKey, VerifyKey
from nacl.exceptions import BadSignatureError
from nacl.encoding import HexEncoder

from app.config import settings

logger = structlog.get_logger()


# Directory for storing agent keys
KEYS_DIR = Path(settings.ca_keys_dir) / "agent_keys"


class AgentKeyManager:
    """
    Manages Ed25519 key pairs for agents.

    Keys are used for:
    - Signing nonces in trust verification
    - Signing messages in TACP protocol
    - Verifying signatures from other agents
    """

    def __init__(self, keys_dir: Optional[Path] = None) -> None:
        """
        Initialize the key manager.

        Args:
            keys_dir: Directory to store keys (defaults to KEYS_DIR)
        """
        self.keys_dir = keys_dir or KEYS_DIR
        self.keys_dir.mkdir(parents=True, exist_ok=True)

        # Cache of loaded keys
        self._signing_keys: dict[UUID, SigningKey] = {}
        self._verify_keys: dict[UUID, VerifyKey] = {}

    def _get_key_path(self, agent_id: UUID, key_type: str) -> Path:
        """Get the path to a key file."""
        return self.keys_dir / f"{agent_id}.{key_type}.key"

    async def generate_keypair(self, agent_id: UUID) -> tuple[str, str]:
        """
        Generate a new Ed25519 keypair for an agent.

        Args:
            agent_id: The agent's ID

        Returns:
            Tuple of (public_key_hex, private_key_hex)
        """
        # Generate new keypair
        signing_key = SigningKey.generate()
        verify_key = signing_key.verify_key

        # Save keys to files
        private_path = self._get_key_path(agent_id, "private")
        public_path = self._get_key_path(agent_id, "public")

        private_path.write_bytes(signing_key.encode())
        public_path.write_bytes(verify_key.encode())

        # Secure the private key file
        os.chmod(private_path, 0o600)

        # Cache the keys
        self._signing_keys[agent_id] = signing_key
        self._verify_keys[agent_id] = verify_key

        logger.info("Generated keypair for agent", agent_id=str(agent_id))

        return (
            verify_key.encode(encoder=HexEncoder).decode(),
            signing_key.encode(encoder=HexEncoder).decode(),
        )

    async def load_signing_key(self, agent_id: UUID) -> Optional[SigningKey]:
        """Load an agent's signing key."""
        if agent_id in self._signing_keys:
            return self._signing_keys[agent_id]

        private_path = self._get_key_path(agent_id, "private")
        if not private_path.exists():
            logger.warning("Private key not found", agent_id=str(agent_id))
            return None

        try:
            key_bytes = private_path.read_bytes()
            signing_key = SigningKey(key_bytes)
            self._signing_keys[agent_id] = signing_key
            return signing_key
        except Exception as e:
            logger.error("Failed to load private key", agent_id=str(agent_id), error=str(e))
            return None

    async def load_verify_key(self, agent_id: UUID) -> Optional[VerifyKey]:
        """Load an agent's verify (public) key."""
        if agent_id in self._verify_keys:
            return self._verify_keys[agent_id]

        public_path = self._get_key_path(agent_id, "public")
        if not public_path.exists():
            logger.warning("Public key not found", agent_id=str(agent_id))
            return None

        try:
            key_bytes = public_path.read_bytes()
            verify_key = VerifyKey(key_bytes)
            self._verify_keys[agent_id] = verify_key
            return verify_key
        except Exception as e:
            logger.error("Failed to load public key", agent_id=str(agent_id), error=str(e))
            return None

    async def load_verify_key_from_hex(self, public_key_hex: str) -> VerifyKey:
        """Load a verify key from hex-encoded string."""
        return VerifyKey(public_key_hex.encode(), encoder=HexEncoder)

    async def sign_message(self, agent_id: UUID, message: str) -> Optional[str]:
        """
        Sign a message with an agent's private key.

        Args:
            agent_id: The agent's ID
            message: The message to sign

        Returns:
            Hex-encoded signature, or None if key not found
        """
        signing_key = await self.load_signing_key(agent_id)
        if not signing_key:
            return None

        signed = signing_key.sign(message.encode())
        signature = signed.signature

        return signature.hex()

    async def verify_signature(
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
            message: The original message
            signature_hex: Hex-encoded signature
            public_key_hex: Optional public key (uses stored key if not provided)

        Returns:
            True if signature is valid
        """
        try:
            if public_key_hex:
                verify_key = await self.load_verify_key_from_hex(public_key_hex)
            else:
                verify_key = await self.load_verify_key(agent_id)
                if not verify_key:
                    return False

            signature = bytes.fromhex(signature_hex)
            verify_key.verify(message.encode(), signature)
            return True

        except BadSignatureError:
            logger.warning("Invalid signature", agent_id=str(agent_id))
            return False
        except Exception as e:
            logger.error("Signature verification error", agent_id=str(agent_id), error=str(e))
            return False

    async def get_public_key_hex(self, agent_id: UUID) -> Optional[str]:
        """Get an agent's public key as hex string."""
        verify_key = await self.load_verify_key(agent_id)
        if not verify_key:
            return None
        return verify_key.encode(encoder=HexEncoder).decode()

    async def has_keypair(self, agent_id: UUID) -> bool:
        """Check if an agent has a keypair."""
        private_path = self._get_key_path(agent_id, "private")
        public_path = self._get_key_path(agent_id, "public")
        return private_path.exists() and public_path.exists()

    async def delete_keypair(self, agent_id: UUID) -> bool:
        """Delete an agent's keypair."""
        private_path = self._get_key_path(agent_id, "private")
        public_path = self._get_key_path(agent_id, "public")

        deleted = False
        if private_path.exists():
            private_path.unlink()
            deleted = True
        if public_path.exists():
            public_path.unlink()
            deleted = True

        self._signing_keys.pop(agent_id, None)
        self._verify_keys.pop(agent_id, None)

        if deleted:
            logger.info("Deleted keypair for agent", agent_id=str(agent_id))

        return deleted


# Global key manager instance
_key_manager: Optional[AgentKeyManager] = None


def get_key_manager() -> AgentKeyManager:
    """Get the global key manager instance."""
    global _key_manager
    if _key_manager is None:
        _key_manager = AgentKeyManager()
    return _key_manager


# Convenience functions
async def generate_agent_keypair(agent_id: UUID) -> tuple[str, str]:
    """Generate a keypair for an agent."""
    return await get_key_manager().generate_keypair(agent_id)


async def sign_nonce(agent_id: UUID, nonce: str) -> str:
    """Sign a nonce with an agent's private key."""
    signature = await get_key_manager().sign_message(agent_id, nonce)
    if signature is None:
        raise ValueError(f"No private key found for agent {agent_id}")
    return signature


async def verify_signature(
    agent_id: UUID,
    message: str,
    signature: str,
    public_key_hex: Optional[str] = None,
) -> bool:
    """Verify a signature."""
    return await get_key_manager().verify_signature(
        agent_id, message, signature, public_key_hex
    )


async def get_agent_public_key(agent_id: UUID) -> Optional[str]:
    """Get an agent's public key."""
    return await get_key_manager().get_public_key_hex(agent_id)


async def ensure_agent_has_keypair(agent_id: UUID) -> str:
    """Ensure an agent has a keypair, generating one if needed."""
    manager = get_key_manager()
    if not await manager.has_keypair(agent_id):
        public_key, _ = await manager.generate_keypair(agent_id)
        return public_key
    return await manager.get_public_key_hex(agent_id) or ""
