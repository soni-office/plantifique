"""
Redis client with connection pooling and graceful degradation.

Local dev  → redis://localhost:6379  (plain TCP)
Upstash    → rediss://:password@host:port  (TLS, same redis protocol)

Two clients are exposed:
  get_redis()        → sync redis.Redis       — use inside thread-pool code
                        (LangGraph nodes, sync services)
  get_async_redis()  → redis.asyncio.Redis    — use from async route handlers
                        and async cache helpers; never blocks the event loop

The clients NEVER raise — any Redis error is logged and None is returned,
so the rest of the app falls back to the source-of-truth (DB / TikTok API).
"""
import logging
from typing import Optional

import redis
import redis.asyncio as aioredis
from redis import Redis

from app.core.config import settings

logger = logging.getLogger(__name__)

_pool: Optional[redis.ConnectionPool] = None
_async_pool: Optional[aioredis.ConnectionPool] = None

_POOL_KWARGS = dict(
    decode_responses=True,
    # 2 workers × 2 pools (sync + async) × 6 = 24 total connections — safely under Upstash free tier (30 limit).
    # If you add more workers or upgrade Upstash, raise this accordingly.
    max_connections=6,
    socket_connect_timeout=2,   # fail fast on bad URL
    socket_timeout=2,
)


# ── Sync client (for thread-pool / LangGraph nodes) ───────────────────────

def _get_pool() -> Optional[redis.ConnectionPool]:
    global _pool
    if _pool is None:
        try:
            _pool = redis.ConnectionPool.from_url(
                settings.REDIS_URL,
                **_POOL_KWARGS,
                retry_on_timeout=False,
            )
            logger.info("Redis sync pool initialised (%s)", settings.REDIS_URL)
        except Exception as exc:
            logger.warning("Redis sync pool init failed — caching disabled: %s", exc)
    return _pool


def get_redis() -> Optional[Redis]:
    """Return a live sync Redis client, or None if Redis is unreachable."""
    pool = _get_pool()
    if pool is None:
        return None
    try:
        client = Redis(connection_pool=pool)
        client.ping()
        return client
    except Exception as exc:
        logger.warning("Redis (sync) unavailable — cache miss forced: %s", exc)
        return None


def ping_redis() -> bool:
    """Sync health-check used at startup."""
    r = get_redis()
    if r:
        logger.info("Redis OK")
        return True
    logger.warning("Redis not reachable")
    return False


# ── Async client (for async route handlers) ───────────────────────────────

def _get_async_pool() -> Optional[aioredis.ConnectionPool]:
    global _async_pool
    if _async_pool is None:
        try:
            _async_pool = aioredis.ConnectionPool.from_url(
                settings.REDIS_URL,
                **_POOL_KWARGS,
            )
            logger.info("Redis async pool initialised (%s)", settings.REDIS_URL)
        except Exception as exc:
            logger.warning("Redis async pool init failed — async caching disabled: %s", exc)
    return _async_pool


def get_async_redis() -> Optional[aioredis.Redis]:
    """
    Return an async Redis client for use in async contexts.

    This call is synchronous (returns a client object, not a coroutine).
    The individual operations (get, set, …) are awaitable.
    """
    pool = _get_async_pool()
    if pool is None:
        return None
    return aioredis.Redis(connection_pool=pool)
