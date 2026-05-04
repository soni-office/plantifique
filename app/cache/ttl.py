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

# ── Org list (Firestore) ───────────────────────────────────────────────
ORG_LIST       = _ttl("CACHE_TTL_ORG_LIST",        3600)  # 1 hr

# ── Sample requests (Firestore) ───────────────────────────────────────────
# Invalidated explicitly: sync, evaluate, review-status, and feedback all
# call invalidate_prefix(sample_list_prefix(org_id)) after mutating state.
SAMPLE_LIST    = _ttl("CACHE_TTL_SAMPLE_LIST",     300)  # 5 min

# --- TIKAPI -------------
TIKAPI_CREATOR_PROFILE = _ttl("CACHE_TTL_TIKAPI_CREATOR_PROFILE", 3600)  # 1 hour
TIKAPI_CREATOR_TOP_VIDEOS = _ttl("CACHE_TTL_TIKAPI_CREATOR_TOP_VIDEOS", 2100)  # 35 min
TIKAPI_CREATOR_PLAYLISTS = _ttl("CACHE_TTL_TIKAPI_CREATOR_PLAYLISTS", 2100)  # 35 min
TIKAPI_VIDEOS_COMMENTS = _ttl("CACHE_TTL_TIKAPI_VIDEOS_COMMENTS", 2100)  # 35 min
