"""Certificate Revocation List (CRL) management."""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Set
from uuid import UUID

import structlog
from redis.asyncio import Redis

from app.core.redis import get_redis

logger = structlog.get_logger()


class CertificateRevocationList:
    """
    Manages the Certificate Revocation List (CRL).

    Uses Redis for fast lookup of revoked certificates.
    """

    REDIS_KEY = "trustmodel:crl"
    REDIS_SET_KEY = "trustmodel:crl:set"

    async def add(
        self,
        certificate_id: UUID,
        reason: str,
        revoked_at: datetime,
    ) -> None:
        """
        Add a certificate to the revocation list.

        Args:
            certificate_id: ID of the revoked certificate
            reason: Reason for revocation
            revoked_at: Timestamp of revocation
        """
        redis = await get_redis()

        entry = {
            "certificate_id": str(certificate_id),
            "reason": reason,
            "revoked_at": revoked_at.isoformat(),
        }

        # Add to set for fast lookup
        await redis.sadd(self.REDIS_SET_KEY, str(certificate_id))

        # Add details to hash
        await redis.hset(
            self.REDIS_KEY,
            str(certificate_id),
            json.dumps(entry),
        )

        logger.info(
            "Certificate added to CRL",
            certificate_id=str(certificate_id),
            reason=reason,
        )

    async def remove(self, certificate_id: UUID) -> None:
        """
        Remove a certificate from the revocation list.

        This is typically used when a certificate expires or is superseded.
        """
        redis = await get_redis()

        await redis.srem(self.REDIS_SET_KEY, str(certificate_id))
        await redis.hdel(self.REDIS_KEY, str(certificate_id))

        logger.info(
            "Certificate removed from CRL",
            certificate_id=str(certificate_id),
        )

    async def is_revoked(self, certificate_id: UUID) -> bool:
        """
        Check if a certificate is revoked.

        Args:
            certificate_id: ID of the certificate to check

        Returns:
            True if the certificate is in the CRL
        """
        redis = await get_redis()
        return await redis.sismember(self.REDIS_SET_KEY, str(certificate_id))

    async def get_revocation_info(
        self,
        certificate_id: UUID,
    ) -> Dict[str, Any] | None:
        """
        Get revocation details for a certificate.

        Args:
            certificate_id: ID of the certificate

        Returns:
            Revocation info dict or None if not revoked
        """
        redis = await get_redis()
        data = await redis.hget(self.REDIS_KEY, str(certificate_id))

        if data:
            return json.loads(data)
        return None

    async def get_all_revoked(self) -> List[Dict[str, Any]]:
        """
        Get all revoked certificates.

        Returns:
            List of revocation entries
        """
        redis = await get_redis()
        all_entries = await redis.hgetall(self.REDIS_KEY)

        return [json.loads(entry) for entry in all_entries.values()]

    async def get_revoked_count(self) -> int:
        """Get the number of revoked certificates."""
        redis = await get_redis()
        return await redis.scard(self.REDIS_SET_KEY)

    async def sync_from_database(
        self,
        revocations: List[Dict[str, Any]],
    ) -> None:
        """
        Sync the CRL from database records.

        This should be called on startup to ensure Redis is in sync.

        Args:
            revocations: List of revocation records from database
        """
        redis = await get_redis()

        # Clear existing CRL
        await redis.delete(self.REDIS_KEY)
        await redis.delete(self.REDIS_SET_KEY)

        # Add all revocations
        for rev in revocations:
            await self.add(
                certificate_id=UUID(rev["certificate_id"]),
                reason=rev["reason"],
                revoked_at=datetime.fromisoformat(rev["revoked_at"]),
            )

        logger.info(
            "CRL synced from database",
            count=len(revocations),
        )


# Global CRL instance
crl = CertificateRevocationList()
