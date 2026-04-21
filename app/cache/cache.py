"""
Core cache operations — both sync and async variants.

All functions are fail-safe: a Redis error is logged and the caller falls
through to the real data source.  The app never crashes due to Redis.

Sync API  (use inside LangGraph nodes / thread-pool code)
─────────────────────────────────────────────────────────
  cache_or_fetch(key, ttl, fn)
      fn is a zero-argument *sync* callable (lambda).

  invalidate(*keys)
  invalidate_prefix(prefix)

Async API  (use from async FastAPI route handlers)
──────────────────────────────────────────────────
  async_cache_or_fetch(key, ttl, fn)
      fn is a zero-argument *async* callable (coroutine function).

  async_invalidate(*keys)
  async_invalidate_prefix(prefix)
"""
import json
import logging
from typing import Any, Callable, Awaitable

from app.core.redis_client import get_redis, get_async_redis

logger = logging.getLogger(__name__)


# ── Sync low-level helpers ─────────────────────────────────────────────────

def _get(key: str) -> Any | None:
    r = get_redis()
    if r is None:
        return None
    try:
        raw = r.get(key)
        return json.loads(raw) if raw is not None else None
    except Exception as exc:
        logger.warning("Cache GET failed key=%s: %s", key, exc)
        return None


def _set(key: str, value: Any, ttl: int) -> None:
    r = get_redis()
    if r is None:
        return
    try:
        r.set(key, json.dumps(value, default=str), ex=ttl)
    except Exception as exc:
        logger.warning("Cache SET failed key=%s: %s", key, exc)


def _delete(*keys: str) -> None:
    r = get_redis()
    if r is None:
        return
    try:
        r.delete(*keys)
    except Exception as exc:
        logger.warning("Cache DELETE failed keys=%s: %s", keys, exc)


def _scan_delete(prefix: str) -> int:
    """Delete all keys matching prefix* using SCAN (non-blocking on Redis side)."""
    r = get_redis()
    if r is None:
        return 0
    deleted = 0
    try:
        cursor = 0
        pattern = f"{prefix}*"
        while True:
            cursor, keys = r.scan(cursor, match=pattern, count=200)
            if keys:
                r.delete(*keys)
                deleted += len(keys)
            if cursor == 0:
                break
    except Exception as exc:
        logger.warning("Cache SCAN-DELETE failed prefix=%s: %s", prefix, exc)
    return deleted


# ── Async low-level helpers ────────────────────────────────────────────────

async def _aget(key: str) -> Any | None:
    r = get_async_redis()
    if r is None:
        return None
    try:
        raw = await r.get(key)
        return json.loads(raw) if raw is not None else None
    except Exception as exc:
        logger.warning("Cache GET (async) failed key=%s: %s", key, exc)
        return None


async def _aset(key: str, value: Any, ttl: int) -> None:
    r = get_async_redis()
    if r is None:
        return
    try:
        await r.set(key, json.dumps(value, default=str), ex=ttl)
    except Exception as exc:
        logger.warning("Cache SET (async) failed key=%s: %s", key, exc)


async def _adelete(*keys: str) -> None:
    r = get_async_redis()
    if r is None:
        return
    try:
        await r.delete(*keys)
    except Exception as exc:
        logger.warning("Cache DELETE (async) failed keys=%s: %s", keys, exc)


async def _ascan_delete(prefix: str) -> int:
    """Async SCAN-based delete — non-blocking on both the Redis and Python sides."""
    r = get_async_redis()
    if r is None:
        return 0
    deleted = 0
    try:
        pattern = f"{prefix}*"
        async for key in r.scan_iter(match=pattern, count=200):
            await r.delete(key)
            deleted += 1
    except Exception as exc:
        logger.warning("Cache SCAN-DELETE (async) failed prefix=%s: %s", prefix, exc)
    return deleted


# ── Sync public API ────────────────────────────────────────────────────────

def cache_or_fetch(key: str, ttl: int, fn: Callable[[], Any]) -> Any:
    """
    Return the cached value for key if present; otherwise call fn() (sync),
    store the result, and return it.

    Use this from LangGraph nodes and other synchronous (thread-pool) callers.
    """
    cached = _get(key)
    if cached is not None:
        logger.info("Cache HIT  %s", key)
        return cached

    logger.info("Cache MISS %s", key)
    result = fn()
    if result is not None:
        _set(key, result, ttl)
    return result


def invalidate(*keys: str) -> None:
    """Delete one or more exact cache keys (sync)."""
    if keys:
        logger.debug("Cache INVALIDATE %s", keys)
        _delete(*keys)


def invalidate_prefix(prefix: str) -> int:
    """Delete all cache keys that start with prefix (sync). Returns count removed."""
    count = _scan_delete(prefix)
    logger.debug("Cache INVALIDATE prefix=%s removed=%s", prefix, count)
    return count


# ── Async public API ───────────────────────────────────────────────────────

async def async_cache_or_fetch(
    key: str,
    ttl: int,
    fn: Callable[[], Awaitable[Any]],
) -> Any:
    """
    Async version of cache_or_fetch. fn must be a zero-argument *async* callable.

    Use this from async FastAPI route handlers so Redis I/O never blocks the
    event loop.

    Example:
        result = await async_cache_or_fetch(
            keys.product_detail(org_id, product_id),
            ttl.PRODUCT_DETAIL,
            lambda: some_async_fetch_fn(org_id, product_id),
        )
    """
    cached = await _aget(key)
    if cached is not None:
        logger.info("Cache HIT  %s", key)
        return cached

    logger.info("Cache MISS %s", key)
    result = await fn()
    if result is not None:
        await _aset(key, result, ttl)
    return result


async def async_invalidate(*keys: str) -> None:
    """Delete one or more exact cache keys (async)."""
    if keys:
        logger.debug("Cache INVALIDATE (async) %s", keys)
        await _adelete(*keys)


async def async_invalidate_prefix(prefix: str) -> int:
    """Delete all cache keys that start with prefix (async). Returns count removed."""
    count = await _ascan_delete(prefix)
    logger.debug("Cache INVALIDATE prefix=%s removed=%s (async)", prefix, count)
    return count
