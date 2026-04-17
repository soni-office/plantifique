"""
Tier configuration management — creator/product tier lists + Tier 5 thresholds.
All business logic for resolving TikTok metadata, caching, and repo writes lives here.
"""
import logging
from typing import Optional

from app.repository.tier_config_repository import TierConfigRepository, THRESHOLD_KEYS
from app.services.creator_service import CreatorService
from app.services.product_service import ProductService, shape_product

logger = logging.getLogger(__name__)


class TierConfigService:

    def __init__(self):
        self.repo = TierConfigRepository()
        self.creator_svc = CreatorService()
        self.product_svc = ProductService()

    # ── Creators (Tier 1 / 2) ─────────────────────────────────────────────

    def list_creators(self, org_id: str, tier: Optional[str] = None) -> list:
        return self.repo.list_creators(org_id=org_id, tier=tier)

    def add_creator(
        self,
        org_id: str,
        username: str,
        tier: str,
        added_by: str,
    ) -> dict:
        """
        Add a creator to Tier 1 or 2.
        Searches TikTok to resolve creator_open_id and avatar_url automatically.
        """
        creator_open_id = ""
        avatar_url = ""
        try:
            res = self.creator_svc.search(org_id=org_id, keyword=username, page_size=12)
            creators = res.get("data", {}).get("creators") or []
            match = next(
                (c for c in creators if c.get("username", "").lower() == username.lower()),
                None,
            )
            if match:
                creator_open_id = match.get("creator_open_id", "")
                avatar_raw = match.get("avatar", {}).get("url", None) or ""
                if isinstance(avatar_raw, dict):
                    url_list = avatar_raw.get("url_list") or []
                    avatar_url = url_list[0] if url_list else ""
                else:
                    avatar_url = avatar_raw
            else:
                logger.warning("Username %s not found in TikTok creator search", username)
        except Exception as exc:
            logger.warning("Could not resolve creator_open_id for %s: %s", username, exc)

        entry = self.repo.upsert_creator(
            org_id=org_id,
            username=username,
            tier=tier,
            creator_open_id=creator_open_id,
            avatar_url=avatar_url,
            added_by=added_by,
        )
        logger.info("Creator added to %s username=%s by=%s", tier, username, added_by)
        return entry

    def remove_creator(self, org_id: str, username: str) -> bool:
        return self.repo.remove_creator(org_id=org_id, username=username)

    # ── Products (Tier 3 / 4) ─────────────────────────────────────────────

    def get_shop_products(self, org_id: str, page_size: int = 50) -> list:
        """Return shaped live shop products for the picker UI."""
        return self.product_svc.get_shop_products_shaped(org_id=org_id, page_size=page_size)

    def list_products(self, org_id: str, tier: Optional[str] = None) -> list:
        return self.repo.list_products(org_id=org_id, tier=tier)

    def add_product(
        self,
        org_id: str,
        product_id: str,
        tier: str,
        thresholds: dict,
        added_by: str,
    ) -> dict:
        """
        Add a product to Tier 3 or 4.
        Fetches TikTok product detail to resolve title, image, price, category.
        Raises LookupError if the product is not found.
        """
        res = self.product_svc.get_detail(org_id=org_id, product_id=product_id)
        product = res.get("data") or {}
        if not product:
            raise LookupError(f"Product '{product_id}' not found in TikTok Shop.")

        shaped = shape_product(product)
        entry = self.repo.upsert_product(
            org_id=org_id,
            product_id=product_id,
            tier=tier,
            title=shaped["title"],
            sku_image_url=shaped["image_url"],
            thresholds=thresholds,
            added_by=added_by,
            price=shaped["price"],
            currency=shaped["currency"],
            category=shaped["category"],
        )
        logger.info("Product added to %s id=%s by=%s", tier, product_id, added_by)
        return entry

    def update_product_thresholds(
        self,
        org_id: str,
        product_id: str,
        thresholds: dict,
        updated_by: str,
    ) -> dict:
        """
        Update thresholds for an existing tier product.
        Raises LookupError if the product is not in tier config.
        """
        existing = self.repo.get_product_config(org_id, product_id)
        if not existing:
            raise LookupError("Product not in tier config")

        return self.repo.upsert_product(
            org_id=org_id,
            product_id=product_id,
            tier=existing["tier"],
            title=existing["title"],
            sku_image_url=existing.get("sku_image_url", ""),
            thresholds=thresholds,
            added_by=updated_by,
            price=existing.get("price", ""),
            currency=existing.get("currency", ""),
            category=existing.get("category", ""),
        )

    def remove_product(self, org_id: str, product_id: str) -> bool:
        return self.repo.remove_product(org_id=org_id, product_id=product_id)

    # ── Tier 5 global thresholds ──────────────────────────────────────────

    def get_tier5(self, org_id: str) -> dict:
        return {
            "thresholds": self.repo.get_tier5_thresholds(org_id),
            "threshold_keys": THRESHOLD_KEYS,
        }

    def set_tier5(self, org_id: str, thresholds: dict, updated_by: str) -> dict:
        result = self.repo.set_tier5_thresholds(
            org_id=org_id,
            thresholds=thresholds,
            updated_by=updated_by,
        )
        logger.info("Tier 5 thresholds updated org=%s by=%s", org_id, updated_by)
        return {"thresholds": result}
