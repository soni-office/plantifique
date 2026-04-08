"""
Firestore collections:

  creator_tier_list/{org_id}_{username}
    org_id, tier, username, creator_open_id, added_by, added_at

  product_tier_config/{org_id}_{product_id}
    org_id, tier, title, price, currency, category, thresholds{...}, added_by, updated_at

  tier5_config/{org_id}
    org_id, min_last_30_days_gmv, min_follower_count, min_post_rate,
    min_content_count, min_ec_video_views, updated_by, updated_at

All reads, writes, and deletes are scoped to the caller's org_id.
"""
from datetime import datetime, timezone
from app.db.firestore import db

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
        return {"id": username, **data}

    def remove_creator(self, org_id: str, username: str) -> bool:
        doc_ref = self.creators.document(_creator_doc_id(org_id, username))
        if not doc_ref.get().exists:
            return False
        doc_ref.delete()
        return True

    def list_creators(self, org_id: str, tier: str | None = None) -> list[dict]:
        query = self.creators.where("org_id", "==", org_id)
        if tier:
            query = query.where("tier", "==", tier)
        return [{**d.to_dict(), "id": d.to_dict().get("username", d.id)} for d in query.stream()]

    # ── Product tier config (Tier 3 / Tier 4) ────────────────────────────

    def get_product_config(self, org_id: str, product_id: str) -> dict | None:
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
        return {"id": product_id, **data}

    def remove_product(self, org_id: str, product_id: str) -> bool:
        doc_ref = self.products.document(_product_doc_id(org_id, product_id))
        if not doc_ref.get().exists:
            return False
        doc_ref.delete()
        return True

    def list_products(self, org_id: str, tier: str | None = None) -> list[dict]:
        query = self.products.where("org_id", "==", org_id)
        if tier:
            query = query.where("tier", "==", tier)
        # Return product_id (not the composite doc id) as "id"
        result = []
        for d in query.stream():
            data = d.to_dict()
            # doc id format is {org_id}__{product_id}
            product_id = d.id.split("__", 1)[-1] if "__" in d.id else d.id
            result.append({**data, "id": product_id})
        return result

    # ── Tier 5 global thresholds (per org) ───────────────────────────────

    def get_tier5_thresholds(self, org_id: str) -> dict:
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
        return {k: clean.get(k) for k in THRESHOLD_KEYS}
