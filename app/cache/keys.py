"""
All cache key builders in one place.

Format: {namespace}:{org_id}:{discriminator}

Keeping keys human-readable (not hashed) makes debugging with redis-cli easy.
Every key is org-scoped so multi-tenant isolation is guaranteed at the key level.
"""


# ── TikTok API ────────────────────────────────────────────────────────────

def shop_cipher(org_id: str) -> str:
    return f"shop:cipher:{org_id}"


def creator_search(org_id: str, keyword: str | None, page_size: int) -> str:
    kw = (keyword or "").lower().strip().replace(" ", "_")
    return f"tiktok:creator:search:{org_id}:{kw}:{page_size}"


def creator_detail(org_id: str, creator_open_id: str) -> str:
    return f"tiktok:creator:detail:{org_id}:{creator_open_id}"


def product_search(org_id: str, page_size: int) -> str:
    return f"tiktok:product:search:{org_id}:{page_size}"


def product_detail(org_id: str, product_id: str) -> str:
    return f"tiktok:product:detail:{org_id}:{product_id}"


def shop_products(org_id: str, page_size: int) -> str:
    """Shaped shop products list for the tier config product picker."""
    return f"tiktok:shop:products:{org_id}:{page_size}"


# ── Tier configuration (Firestore) ────────────────────────────────────────

def tier_creators_list(org_id: str) -> str:
    return f"tier:creators:{org_id}"


def tier_creator(org_id: str, username: str) -> str:
    return f"tier:creator:{org_id}:{username.lower()}"


def tier_products_list(org_id: str) -> str:
    return f"tier:products:{org_id}"


def tier_product(org_id: str, product_id: str) -> str:
    return f"tier:product:{org_id}:{product_id}"


def tier5(org_id: str) -> str:
    return f"tier:tier5:{org_id}"


# ── Sample requests (Firestore) ───────────────────────────────────────────

def sample_list(org_id: str, page_size: int, cursor: str | None) -> str:
    cur = cursor or "first"
    return f"samples:list:{org_id}:{page_size}:{cur}"


def sample_list_prefix(org_id: str) -> str:
    """Prefix used to wipe all paginated pages for an org at once."""
    return f"samples:list:{org_id}:"


def sample_item(org_id: str, sample_id: str) -> str:
    return f"samples:item:{org_id}:{sample_id}"
