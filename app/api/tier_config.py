"""
/config/tier  — admin-only tier configuration endpoints.

Tier 1 / 2  → creator_tier_list (keyed by username)
Tier 3 / 4  → product_tier_config (keyed by product_id)
Tier 5      → single threshold document
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.auth_session import require_role
from app.repository.tier_config_repository import TierConfigRepository, THRESHOLD_KEYS
from app.services.tiktok.product_service import TikTokProductService
from app.services.tiktok.creator_service import TikTokCreatorService
from app.services.tiktok.token_service import TokenService
from app.utils.shop_ciphers import shop_cipher
from app.cache import cache, keys, ttl

router = APIRouter(prefix="/config/tier", tags=["Tier Config"])
logger = logging.getLogger(__name__)
_admin = require_role("ORG_ADMIN", "SUPER_ADMIN")


# ── Helper ────────────────────────────────────────────────────────────────

def _tokens(org_id: str) -> tuple[str, str]:
    at = TokenService().get_valid_access_token(org_id)
    breakpoint()
    cipher = shop_cipher(org_id)["data"]["shops"][0]["cipher"]
    return at, cipher


# ══════════════════════════════════════════════════════════════════════════
# Creator lists  (Tier 1 / 2)
# ══════════════════════════════════════════════════════════════════════════

class AddCreatorBody(BaseModel):
    username: str
    tier: str   # "TIER_1" | "TIER_2"


@router.get("/creators")
async def list_tier_creators(
    tier: str | None = None,
    caller=Depends(_admin),
):
    """List all creators on Tier 1 or Tier 2 lists. Pass ?tier=TIER_1 to filter."""
    return {"creators": TierConfigRepository().list_creators(org_id=caller["org_id"], tier=tier)}


@router.post("/creators", status_code=status.HTTP_201_CREATED)
async def add_creator(body: AddCreatorBody, caller=Depends(_admin)):
    """
    Add a creator to Tier 1 or Tier 2 by username.
    Searches TikTok marketplace to resolve the creator_open_id automatically.
    Raises 404 if the username is not found.
    """
    repo = TierConfigRepository()

    # Try to resolve creator_open_id and avatar_url via TikTok creator search
    creator_open_id = ""
    avatar_url = ""
    try:
        org_id = caller["org_id"]
        at, cipher = _tokens(org_id)

        res = cache.cache_or_fetch(
            keys.creator_search(org_id, body.username, 12),
            ttl.CREATOR_SEARCH,
            lambda: TikTokCreatorService.search(
                access_token=at,
                shop_cipher=cipher,
                keyword=body.username,
                page_size=12,
            ),
        )
        creators = res.get("data", {}).get("creators") or []
        # Find exact username match (case-insensitive)
        match = next(
            (c for c in creators if c.get("username", "").lower() == body.username.lower()),
            None,
        )
        if match:
            creator_open_id = match.get("creator_open_id", "")
            # TikTok sometimes returns avatar as a plain string, sometimes as
            # {"url_list": ["https://..."], "width": ..., "height": ...}
            avatar_raw = (
                match.get("avatar", {}).get("url", None)
                or ""
            )
            if isinstance(avatar_raw, dict):
                url_list = avatar_raw.get("url_list") or []
                avatar_url = url_list[0] if url_list else ""
            else:
                avatar_url = avatar_raw or ""
        else:
            logger.warning("Username %s not found in TikTok creator search", body.username)
    except Exception as exc:
        # Non-fatal — we still add the creator, open_id will be empty
        logger.warning("Could not resolve creator_open_id for %s: %s", body.username, exc)

    entry = repo.upsert_creator(
        org_id=caller["org_id"],
        username=body.username,
        tier=body.tier,
        creator_open_id=creator_open_id,
        avatar_url=avatar_url,
        added_by=caller["uid"],
    )
    logger.info("Creator added to %s username=%s by=%s", body.tier, body.username, caller["uid"])
    return entry


@router.delete("/creators/{username}", status_code=status.HTTP_200_OK)
async def remove_creator(username: str, caller=Depends(_admin)):
    removed = TierConfigRepository().remove_creator(org_id=caller["org_id"], username=username)
    if not removed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Creator '{username}' not in tier list")
    logger.info("Creator removed from tier list username=%s by=%s", username, caller["uid"])
    return {"removed": True, "username": username}


# ══════════════════════════════════════════════════════════════════════════
# Product list  (Tier 3 / 4)
# ══════════════════════════════════════════════════════════════════════════

class AddProductBody(BaseModel):
    product_id: str
    tier: str           # "TIER_3" | "TIER_4"
    thresholds: dict = {}


class UpdateThresholdsBody(BaseModel):
    thresholds: dict


def _shape_product(p: dict) -> dict:
    """Normalise a raw TikTok product dict into the picker card shape."""
    main_images = p.get("main_images") or []
    image_url = ""
    if main_images:
        urls = main_images[0].get("thumb_urls") or main_images[0].get("urls") or []
        image_url = urls[0] if urls else ""

    skus = p.get("skus") or []
    price_str = ""
    currency = ""
    if skus:
        price_obj = skus[0].get("price") or {}
        price_str = price_obj.get("sale_price") or price_obj.get("original_price") or ""
        currency = price_obj.get("currency", "USD")

    chains = p.get("category_chains") or []
    category = chains[-1].get("local_name", "") if chains else ""

    return {
        "id": p.get("id") or p.get("product_id", ""),
        "title": p.get("title", ""),
        "image_url": image_url,
        "price": price_str,
        "currency": currency,
        "status": p.get("status", ""),
        "category": category,
    }


@router.get("/products/shop")
async def list_shop_products(
    page_size: int = 50,
    caller=Depends(_admin),
):
    """
    Fetch live shop products from TikTok for the product-picker UI.
    Cached per org + page_size for CACHE_TTL_SHOP_PRODUCTS seconds.
    """
    org_id = caller["org_id"]

    def _fetch():
        at, cipher = _tokens(org_id)
        res = TikTokProductService.search(
            access_token=at,
            shop_cipher=cipher,
            page_size=page_size,
        )
        raw = res.get("data", {}).get("products") or []
        return [_shape_product(p) for p in raw]

    products = cache.cache_or_fetch(
        keys.shop_products(org_id, page_size),
        ttl.SHOP_PRODUCTS,
        _fetch,
    )
    return {"products": products}


@router.get("/products")
async def list_tier_products(tier: str | None = None, caller=Depends(_admin)):
    """List all products in Tier 3/4 config. Pass ?tier=TIER_3 to filter."""
    return {"products": TierConfigRepository().list_products(org_id=caller["org_id"], tier=tier)}


@router.post("/products", status_code=status.HTTP_201_CREATED)
async def add_product(body: AddProductBody, caller=Depends(_admin)):
    """
    Add a product to Tier 3 or 4.
    Fetches live product detail from TikTok to resolve title + image.
    """
    org_id = caller["org_id"]
    at, cipher = _tokens(org_id)

    res = cache.cache_or_fetch(
        keys.product_detail(org_id, body.product_id),
        ttl.PRODUCT_DETAIL,
        lambda: TikTokProductService.get_product_by_id(
            access_token=at,
            shop_cipher=cipher,
            product_id=body.product_id,
        ),
    )
    product = res.get("data") or {}
    if not product:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Product '{body.product_id}' not found in TikTok Shop.",
        )

    shaped = _shape_product(product)

    try:
        entry = TierConfigRepository().upsert_product(
            org_id=caller["org_id"],
            product_id=body.product_id,
            tier=body.tier,
            title=shaped["title"],
            sku_image_url=shaped["image_url"],
            thresholds=body.thresholds,
            added_by=caller["uid"],
            price=shaped["price"],
            currency=shaped["currency"],
            category=shaped["category"],
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))

    logger.info("Product added to %s id=%s by=%s", body.tier, body.product_id, caller["uid"])
    return entry


@router.patch("/products/{product_id}/thresholds")
async def update_product_thresholds(
    product_id: str,
    body: UpdateThresholdsBody,
    caller=Depends(_admin),
):
    """Update the threshold config for an existing tier 3/4 product."""
    repo = TierConfigRepository()
    existing = repo.get_product_config(caller["org_id"], product_id)
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not in tier config")

    updated = repo.upsert_product(
        org_id=caller["org_id"],
        product_id=product_id,
        tier=existing["tier"],
        title=existing["title"],
        sku_image_url=existing.get("sku_image_url", ""),
        thresholds=body.thresholds,
        added_by=caller["uid"],
        price=existing.get("price", ""),
        currency=existing.get("currency", ""),
        category=existing.get("category", ""),
    )
    logger.info("Thresholds updated product_id=%s by=%s", product_id, caller["uid"])
    return updated


@router.delete("/products/{product_id}")
async def remove_product(product_id: str, caller=Depends(_admin)):
    removed = TierConfigRepository().remove_product(org_id=caller["org_id"], product_id=product_id)
    if not removed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not in tier config")
    logger.info("Product removed from tier config id=%s by=%s", product_id, caller["uid"])
    return {"removed": True, "product_id": product_id}


# ══════════════════════════════════════════════════════════════════════════
# Tier 5 global thresholds
# ══════════════════════════════════════════════════════════════════════════

class Tier5Body(BaseModel):
    thresholds: dict


@router.get("/tier5")
async def get_tier5(caller=Depends(_admin)):
    """Get current Tier 5 global thresholds."""
    return {
        "thresholds": TierConfigRepository().get_tier5_thresholds(caller["org_id"]),
        "threshold_keys": THRESHOLD_KEYS,
    }


@router.put("/tier5")
async def set_tier5(body: Tier5Body, caller=Depends(_admin)):
    """Replace Tier 5 global thresholds."""
    result = TierConfigRepository().set_tier5_thresholds(
        org_id=caller["org_id"],
        thresholds=body.thresholds,
        updated_by=caller["uid"],
    )
    logger.info("Tier 5 thresholds updated by=%s", caller["uid"])
    return {"thresholds": result}
