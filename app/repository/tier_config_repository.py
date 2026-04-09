"""
Firestore collections:

  creator_tier_list/{org_id}_{username}
    org_id, tier, username, creator_open_id, avatar_url, added_by, added_at

  product_tier_config/{org_id}_{product_id}
    org_id, tier, title, price, currency, category, thresholds{...}, added_by, updated_at

  tier5_config/{org_id}
    org_id, min_last_30_days_gmv, min_follower_count, min_post_rate,
    min_content_count, min_ec_video_views, updated_by, updated_at

All reads, writes, and deletes are scoped to the caller's org_id.
Reads are served from Redis cache; writes invalidate the relevant keys.
"""
from datetime import datetime, timezone
from google.cloud.firestore import FieldFilter
from app.db.firestore import db
from app.cache import cache, keys, ttl

THRESHOLD_KEYS = [
    "min_last_30_days_gmv",
    "min_follower_count",
    "min_post_rate",
    "min_content_count",
    "min_ec_video_views",
]


def _creator_doc_id(org_id: str, username: str) -> str:
    return f"{org_id}__{username}"


def _product_doc_id(org_id: str, product_id: str) -> str:
    return f"{org_id}__{product_id}"


class TierConfigRepository:

    def __init__(self):
        self.creators = db.collection("creator_tier_list")
        self.products = db.collection("product_tier_config")
        self.tier5_col = db.collection("tier5_config")

    # ── Creator tier list (Tier 1 / Tier 2) ──────────────────────────────

    def get_creator_tier(self, org_id: str, username: str) -> dict | None:
        """Check if a username is on Tier 1/2 for this org. O(1) lookup."""
        return cache.cache_or_fetch(
            keys.tier_creator(org_id, username),
            ttl.TIER_CONFIG,
            lambda: self._fetch_creator_tier(org_id, username),
        )

    def _fetch_creator_tier(self, org_id: str, username: str) -> dict | None:
        doc = self.creators.document(_creator_doc_id(org_id, username)).get()
        if not doc.exists:
            return None
        return {**doc.to_dict(), "id": doc.id}

    def upsert_creator(
        self,
        org_id: str,
        username: str,
        tier: str,
        creator_open_id: str = "",
        avatar_url: str = "",
        added_by: str = "",
    ) -> dict:
        if tier not in ("TIER_1", "TIER_2"):
            raise ValueError("Creator tier must be TIER_1 or TIER_2")
        now = datetime.now(timezone.utc)
        data = {
            "org_id": org_id,
            "tier": tier,
            "username": username,
            "creator_open_id": creator_open_id,
            "avatar_url": avatar_url,
            "added_by": added_by,
            "added_at": now,
        }
        self.creators.document(_creator_doc_id(org_id, username)).set(data, merge=True)
        # Invalidate this creator's lookup + the full list
        cache.invalidate(
            keys.tier_creator(org_id, username),
            keys.tier_creators_list(org_id),
        )
        return {"id": username, **data}

    def remove_creator(self, org_id: str, username: str) -> bool:
        doc_ref = self.creators.document(_creator_doc_id(org_id, username))
        if not doc_ref.get().exists:
            return False
        doc_ref.delete()
        cache.invalidate(
            keys.tier_creator(org_id, username),
            keys.tier_creators_list(org_id),
        )
        return True

    def list_creators(self, org_id: str, tier: str | None = None) -> list[dict]:
        # tier-filtered lists are not cached separately — always use the full list
        # and filter in Python to avoid multiple cache keys
        cache_key = keys.tier_creators_list(org_id)
        all_creators = cache.cache_or_fetch(
            cache_key,
            ttl.TIER_CONFIG,
            lambda: self._fetch_creators(org_id),
        )
        if tier:
            return [c for c in all_creators if c.get("tier") == tier]
        return all_creators

    def _fetch_creators(self, org_id: str) -> list[dict]:
        return [
            {**d.to_dict(), "id": d.to_dict().get("username", d.id)}
            for d in self.creators.where(filter=FieldFilter("org_id", "==", org_id)).stream()
        ]

    # ── Product tier config (Tier 3 / Tier 4) ────────────────────────────

    def get_product_config(self, org_id: str, product_id: str) -> dict | None:
        return cache.cache_or_fetch(
            keys.tier_product(org_id, product_id),
            ttl.TIER_CONFIG,
            lambda: self._fetch_product_config(org_id, product_id),
        )

    def _fetch_product_config(self, org_id: str, product_id: str) -> dict | None:
        doc = self.products.document(_product_doc_id(org_id, product_id)).get()
        if not doc.exists:
            return None
        return {**doc.to_dict(), "id": product_id}

    def upsert_product(
        self,
        org_id: str,
        product_id: str,
        tier: str,
        title: str,
        sku_image_url: str = "",
        thresholds: dict | None = None,
        added_by: str = "",
        price: str = "",
        currency: str = "",
        category: str = "",
    ) -> dict:
        if tier not in ("TIER_3", "TIER_4"):
            raise ValueError("Product tier must be TIER_3 or TIER_4")
        clean = {k: (thresholds or {}).get(k) for k in THRESHOLD_KEYS}
        now = datetime.now(timezone.utc)
        data = {
            "org_id": org_id,
            "tier": tier,
            "title": title,
            "sku_image_url": sku_image_url,
            "price": price,
            "currency": currency,
            "category": category,
            "thresholds": clean,
            "added_by": added_by,
            "updated_at": now,
        }
        self.products.document(_product_doc_id(org_id, product_id)).set(data, merge=True)
        cache.invalidate(
            keys.tier_product(org_id, product_id),
            keys.tier_products_list(org_id),
        )
        return {"id": product_id, **data}

    def remove_product(self, org_id: str, product_id: str) -> bool:
        doc_ref = self.products.document(_product_doc_id(org_id, product_id))
        if not doc_ref.get().exists:
            return False
        doc_ref.delete()
        cache.invalidate(
            keys.tier_product(org_id, product_id),
            keys.tier_products_list(org_id),
        )
        return True

    def list_products(self, org_id: str, tier: str | None = None) -> list[dict]:
        all_products = cache.cache_or_fetch(
            keys.tier_products_list(org_id),
            ttl.TIER_CONFIG,
            lambda: self._fetch_products(org_id),
        )
        if tier:
            return [p for p in all_products if p.get("tier") == tier]
        return all_products

    def _fetch_products(self, org_id: str) -> list[dict]:
        result = []
        for d in self.products.where(filter=FieldFilter("org_id", "==", org_id)).stream():
            data = d.to_dict()
            product_id = d.id.split("__", 1)[-1] if "__" in d.id else d.id
            result.append({**data, "id": product_id})
        return result

    # ── Tier 5 global thresholds (per org) ───────────────────────────────

    def get_tier5_thresholds(self, org_id: str) -> dict:
        return cache.cache_or_fetch(
            keys.tier5(org_id),
            ttl.TIER_CONFIG,
            lambda: self._fetch_tier5(org_id),
        )

    def _fetch_tier5(self, org_id: str) -> dict:
        doc = self.tier5_col.document(org_id).get()
        if not doc.exists:
            return {k: None for k in THRESHOLD_KEYS}
        raw = doc.to_dict()
        return {k: raw.get(k) for k in THRESHOLD_KEYS}

    def set_tier5_thresholds(self, org_id: str, thresholds: dict, updated_by: str = "") -> dict:
        clean = {k: thresholds.get(k) for k in THRESHOLD_KEYS}
        clean["org_id"] = org_id
        clean["updated_by"] = updated_by
        clean["updated_at"] = datetime.now(timezone.utc)
        self.tier5_col.document(org_id).set(clean)
        cache.invalidate(keys.tier5(org_id))
        return {k: clean.get(k) for k in THRESHOLD_KEYS}
