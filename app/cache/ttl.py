"""
Cache TTL constants — all individually configurable via environment variables.

Naming: CACHE_TTL_<DOMAIN>  (seconds)

Defaults balance freshness vs API quota:
  Shop cipher       1 h    — tied to access-token life, rarely rotates
  Creator search    5 min  — keyword results shift slowly
  Creator detail   15 min  — profile metrics change at most daily
  Product search   10 min  — product list changes occasionally
  Product detail   15 min  — product metadata is stable
  Shop products    10 min  — picker list; no need to be live on every open
  Tier config       5 min  — admin changes propagate within minutes
  Sample list       5 min  — between syncs, list is stable; sync invalidates early
  Sample item      10 min  — analysis/review state; explicit invalidation on updates
"""
import os


def _ttl(env_key: str, default: int) -> int:
    return int(os.getenv(env_key, default))


# ── TikTok API ────────────────────────────────────────────────────────────
SHOP_CIPHER    = _ttl("CACHE_TTL_SHOP_CIPHER",    3600)  # 1 h
CREATOR_SEARCH = _ttl("CACHE_TTL_CREATOR_SEARCH",  300)  # 5 min
CREATOR_DETAIL = _ttl("CACHE_TTL_CREATOR_DETAIL",  900)  # 15 min
PRODUCT_SEARCH = _ttl("CACHE_TTL_PRODUCT_SEARCH",  600)  # 10 min
PRODUCT_DETAIL = _ttl("CACHE_TTL_PRODUCT_DETAIL",  900)  # 15 min
SHOP_PRODUCTS  = _ttl("CACHE_TTL_SHOP_PRODUCTS",   600)  # 10 min

# ── Tier config (Firestore) ───────────────────────────────────────────────
TIER_CONFIG    = _ttl("CACHE_TTL_TIER_CONFIG",     300)  # 5 min

# ── Sample requests (Firestore) ───────────────────────────────────────────
# Both are also invalidated explicitly:
#   - Sync → invalidates entire org's sample list
#   - Evaluate / review-status / feedback → invalidates the specific item
SAMPLE_LIST    = _ttl("CACHE_TTL_SAMPLE_LIST",     300)  # 5 min
SAMPLE_ITEM    = _ttl("CACHE_TTL_SAMPLE_ITEM",     600)  # 10 min
