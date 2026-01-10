"""Redis connection and utilities."""

from typing import Optional

import redis.asyncio as redis
from redis.asyncio import Redis

from app.config import settings

# Global Redis connection pool
_redis_pool: Optional[Redis] = None


async def get_redis() -> Redis:
    """
    Get Redis connection from pool.

    Usage:
        redis = await get_redis()
        await redis.set("key", "value")
    """
    global _redis_pool

    if _redis_pool is None:
        _redis_pool = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )

    return _redis_pool


async def close_redis() -> None:
    """Close Redis connection pool."""
    global _redis_pool

    if _redis_pool is not None:
        await _redis_pool.close()
        _redis_pool = None


class RedisCache:
    """
    Redis caching utilities with type-safe operations.
    """

    def __init__(self, prefix: str = "trustmodel:"):
        self.prefix = prefix

    def _key(self, key: str) -> str:
        """Generate prefixed key."""
        return f"{self.prefix}{key}"

    async def get(self, key: str) -> Optional[str]:
        """Get value from cache."""
        r = await get_redis()
        return await r.get(self._key(key))

    async def set(
        self,
        key: str,
        value: str,
        expire_seconds: Optional[int] = None,
    ) -> None:
        """Set value in cache with optional expiration."""
        r = await get_redis()
        if expire_seconds:
            await r.setex(self._key(key), expire_seconds, value)
        else:
            await r.set(self._key(key), value)

    async def delete(self, key: str) -> None:
        """Delete key from cache."""
        r = await get_redis()
        await r.delete(self._key(key))

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        r = await get_redis()
        return bool(await r.exists(self._key(key)))

    async def incr(self, key: str) -> int:
        """Increment counter."""
        r = await get_redis()
        return await r.incr(self._key(key))

    async def expire(self, key: str, seconds: int) -> None:
        """Set expiration on key."""
        r = await get_redis()
        await r.expire(self._key(key), seconds)


# Pre-configured cache instances
cache = RedisCache(prefix="trustmodel:cache:")
rate_limiter = RedisCache(prefix="trustmodel:rate:")
