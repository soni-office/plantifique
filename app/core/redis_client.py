"""
Redis client with connection pooling and graceful degradation.

Local dev  → redis://localhost:6379  (plain TCP)
Upstash    → rediss://:password@host:port  (TLS, same redis protocol)

The client NEVER raises — any Redis error is logged and None is returned,
so the rest of the app falls back to the source-of-truth (DB / TikTok API).
"""
import logging
from typing import Optional

import redis
from redis import Redis

from app.core.config import settings

logger = logging.getLogger(__name__)

_pool: Optional[redis.ConnectionPool] = None


def _get_pool() -> Optional[redis.ConnectionPool]:
    global _pool
    if _pool is None:
        try:
            _pool = redis.ConnectionPool.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                max_connections=20,
                socket_connect_timeout=2,   # fail fast on bad URL
                socket_timeout=2,
                retry_on_timeout=False,
            )
            logger.info("Redis connection pool initialised (%s)", settings.REDIS_URL)
        except Exception as exc:
            logger.warning("Redis pool init failed — caching disabled: %s", exc)
    return _pool


def get_redis() -> Optional[Redis]:
    """Return a live Redis client or None if Redis is unreachable."""
    pool = _get_pool()
    if pool is None:
        return None
    try:
        client = Redis(connection_pool=pool)
        client.ping()
        return client
    except Exception as exc:
        logger.warning("Redis unavailable — cache miss forced: %s", exc)
        return None


def ping_redis() -> bool:
    """Health-check helper used at startup."""
    r = get_redis()
    if r:
        logger.info("Redis OK")
        return True
    logger.warning("Redis not reachable")
    return False
