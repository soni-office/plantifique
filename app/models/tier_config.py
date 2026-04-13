"""
DB models for the three tier-config Firestore collections.

  creator_tier_list  — doc ID: {org_id}__{username}
  product_tier_config — doc ID: {org_id}__{product_id}
  tier5_config        — doc ID: org_id
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal, Optional


CreatorTier = Literal["TIER_1", "TIER_2"]
ProductTier = Literal["TIER_3", "TIER_4"]

THRESHOLD_KEYS = [
    "min_last_30_days_gmv",
    "min_follower_count",
    "min_post_rate",
    "min_content_count",
    "min_ec_video_views",
]


@dataclass
class Thresholds:
    min_last_30_days_gmv: Optional[float] = None
    min_follower_count: Optional[int] = None
    min_post_rate: Optional[float] = None
    min_content_count: Optional[int] = None
    min_ec_video_views: Optional[int] = None

    @classmethod
    def from_dict(cls, data: dict) -> "Thresholds":
        return cls(
            min_last_30_days_gmv=data.get("min_last_30_days_gmv"),
            min_follower_count=data.get("min_follower_count"),
            min_post_rate=data.get("min_post_rate"),
            min_content_count=data.get("min_content_count"),
            min_ec_video_views=data.get("min_ec_video_views"),
        )

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in THRESHOLD_KEYS}


# ── Tier 1 / 2 ────────────────────────────────────────────────────────────

@dataclass
class TierCreator:
    """
    creator_tier_list collection.
    Composite doc ID: {org_id}__{username}
    `id` field exposed as username for API responses.
    """
    id: str                    # username (natural key returned in API)
    org_id: str
    tier: CreatorTier
    username: str
    creator_open_id: str = ""
    avatar_url: str = ""
    added_by: str = ""
    added_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def from_dict(cls, data: dict, doc_id: str = "") -> "TierCreator":
        return cls(
            id=data.get("username") or doc_id.split("__", 1)[-1],
            org_id=data.get("org_id", ""),
            tier=data.get("tier", "TIER_1"),
            username=data.get("username", ""),
            creator_open_id=data.get("creator_open_id", ""),
            avatar_url=data.get("avatar_url", ""),
            added_by=data.get("added_by", ""),
            added_at=data.get("added_at") or datetime.now(timezone.utc),
        )

    def to_dict(self) -> dict:
        return {
            "org_id": self.org_id,
            "tier": self.tier,
            "username": self.username,
            "creator_open_id": self.creator_open_id,
            "avatar_url": self.avatar_url,
            "added_by": self.added_by,
            "added_at": self.added_at,
        }


# ── Tier 3 / 4 ────────────────────────────────────────────────────────────

@dataclass
class TierProduct:
    """
    product_tier_config collection.
    Composite doc ID: {org_id}__{product_id}
    `id` field exposed as product_id for API responses.
    """
    id: str                    # product_id (natural key returned in API)
    org_id: str
    tier: ProductTier
    title: str
    thresholds: Thresholds = field(default_factory=Thresholds)
    sku_image_url: str = ""
    price: str = ""
    currency: str = ""
    category: str = ""
    added_by: str = ""
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def from_dict(cls, data: dict, doc_id: str = "") -> "TierProduct":
        raw_id = doc_id.split("__", 1)[-1] if "__" in doc_id else doc_id
        return cls(
            id=data.get("id") or raw_id,
            org_id=data.get("org_id", ""),
            tier=data.get("tier", "TIER_3"),
            title=data.get("title", ""),
            thresholds=Thresholds.from_dict(data.get("thresholds") or {}),
            sku_image_url=data.get("sku_image_url", ""),
            price=data.get("price", ""),
            currency=data.get("currency", ""),
            category=data.get("category", ""),
            added_by=data.get("added_by", ""),
            updated_at=data.get("updated_at") or datetime.now(timezone.utc),
        )

    def to_dict(self) -> dict:
        return {
            "org_id": self.org_id,
            "tier": self.tier,
            "title": self.title,
            "thresholds": self.thresholds.to_dict(),
            "sku_image_url": self.sku_image_url,
            "price": self.price,
            "currency": self.currency,
            "category": self.category,
            "added_by": self.added_by,
            "updated_at": self.updated_at,
        }


# ── Tier 5 ────────────────────────────────────────────────────────────────

@dataclass
class Tier5Config:
    """
    tier5_config collection.
    Document ID = org_id. One document per org.
    """
    org_id: str
    thresholds: Thresholds = field(default_factory=Thresholds)
    updated_by: str = ""
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def from_dict(cls, data: dict) -> "Tier5Config":
        return cls(
            org_id=data.get("org_id", ""),
            thresholds=Thresholds.from_dict(data),
            updated_by=data.get("updated_by", ""),
            updated_at=data.get("updated_at") or datetime.now(timezone.utc),
        )

    def to_dict(self) -> dict:
        d = self.thresholds.to_dict()
        d.update({
            "org_id": self.org_id,
            "updated_by": self.updated_by,
            "updated_at": self.updated_at,
        })
        return d
