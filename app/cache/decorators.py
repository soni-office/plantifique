"""
Decorator for caching async endpoint responses.
For most use-cases, prefer cache_or_fetch() from cache.py directly.
"""
from functools import wraps

from app.cache.cache import _get, _set


def cache_response(key_fn, ttl: int = 300):
    """
    Cache an async function's return value.

    key_fn: callable that receives the same *args/**kwargs as the function
            and returns the cache key string.

    Example:
        @cache_response(lambda org_id, ps: keys.product_search(org_id, ps), ttl=ttl.PRODUCT_SEARCH)
        async def my_fn(org_id, ps): ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            key = key_fn(*args, **kwargs)
            cached = _get(key)
            if cached is not None:
                return cached
            result = await func(*args, **kwargs)
            if result is not None:
                _set(key, result, ttl)
            return result
        return wrapper
    return decorator
