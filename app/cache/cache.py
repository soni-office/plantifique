"""
Core cache operations.

All functions are fail-safe: a Redis error is logged and the caller falls
through to the real data source.  The app never crashes due to Redis.

Primary API
───────────
  cache_or_fetch(key, ttl, fn)
      Return cached value if present, otherwise call fn(), cache the result,
      and return it.  fn must be a zero-argument callable (use lambdas).

  invalidate(*keys)
      Delete one or more exact keys.

  invalidate_prefix(prefix)
      Delete all keys that start with prefix (uses SCAN — safe on large DBs).
"""
import json
import logging
from typing import Any, Callable

from app.core.redis_client import get_redis

logger = logging.getLogger(__name__)


# ── Low-level helpers ──────────────────────────────────────────────────────

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
    """Delete all keys matching prefix* using SCAN (non-blocking)."""
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


# ── Public API ─────────────────────────────────────────────────────────────

def cache_or_fetch(key: str, ttl: int, fn: Callable[[], Any]) -> Any:
    """
    Return the cached value for key if it exists; otherwise call fn(),
    store the result under key with the given TTL, and return it.

    Usage:
        result = cache_or_fetch(
            keys.product_detail(org_id, product_id),
            ttl.PRODUCT_DETAIL,
            lambda: TikTokProductService.get_product_by_id(at, cipher, product_id),
        )
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
    """Delete one or more exact cache keys."""
    if keys:
        logger.debug("Cache INVALIDATE %s", keys)
        _delete(*keys)


def invalidate_prefix(prefix: str) -> int:
    """
    Delete all cache keys that start with prefix.
    Returns the number of keys removed.
    Used to wipe all paginated pages for a given org at once.
    """
    count = _scan_delete(prefix)
    logger.debug("Cache INVALIDATE prefix=%s removed=%s", prefix, count)
    return count
