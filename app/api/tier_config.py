"""
/config/tier  — admin-only tier configuration endpoints.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.auth_session import require_role
from app.services.tier_config_service import TierConfigService

router = APIRouter(prefix="/config/tier", tags=["Tier Config"])
logger = logging.getLogger(__name__)
_admin = require_role("ORG_ADMIN", "SUPER_ADMIN")


# ══════════════════════════════════════════════════════════════════════════
# Creators (Tier 1 / 2)
# ══════════════════════════════════════════════════════════════════════════

class AddCreatorBody(BaseModel):
    username: str
    tier: str


@router.get("/creators")
async def list_tier_creators(tier: str | None = None, caller=Depends(_admin)):
    """List creators on Tier 1/2. Pass ?tier=TIER_1 to filter."""
    return {"creators": TierConfigService().list_creators(org_id=caller["org_id"], tier=tier)}


@router.post("/creators", status_code=status.HTTP_201_CREATED)
async def add_creator(body: AddCreatorBody, caller=Depends(_admin)):
    """Add a creator to Tier 1 or 2 by username."""
    return TierConfigService().add_creator(
        org_id=caller["org_id"],
        username=body.username,
        tier=body.tier,
        added_by=caller["uid"],
    )


@router.delete("/creators/{username}", status_code=status.HTTP_200_OK)
async def remove_creator(username: str, caller=Depends(_admin)):
    removed = TierConfigService().remove_creator(org_id=caller["org_id"], username=username)
    if not removed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Creator '{username}' not in tier list")
    return {"removed": True, "username": username}


# ══════════════════════════════════════════════════════════════════════════
# Products (Tier 3 / 4)
# ══════════════════════════════════════════════════════════════════════════

class AddProductBody(BaseModel):
    product_id: str
    tier: str
    thresholds: dict = {}


class UpdateThresholdsBody(BaseModel):
    thresholds: dict


@router.get("/products/shop")
async def list_shop_products(page_size: int = 50, caller=Depends(_admin)):
    """Fetch live shop products from TikTok for the product-picker UI."""
    products = TierConfigService().get_shop_products(
        org_id=caller["org_id"], page_size=page_size
    )
    return {"products": products}


@router.get("/products")
async def list_tier_products(tier: str | None = None, caller=Depends(_admin)):
    """List Tier 3/4 products. Pass ?tier=TIER_3 to filter."""
    return {"products": TierConfigService().list_products(org_id=caller["org_id"], tier=tier)}


@router.post("/products", status_code=status.HTTP_201_CREATED)
async def add_product(body: AddProductBody, caller=Depends(_admin)):
    """Add a product to Tier 3 or 4."""
    try:
        return TierConfigService().add_product(
            org_id=caller["org_id"],
            product_id=body.product_id,
            tier=body.tier,
            thresholds=body.thresholds,
            added_by=caller["uid"],
        )
    except LookupError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))


@router.patch("/products/{product_id}/thresholds")
async def update_product_thresholds(
    product_id: str,
    body: UpdateThresholdsBody,
    caller=Depends(_admin),
):
    """Update thresholds for an existing tier 3/4 product."""
    try:
        return TierConfigService().update_product_thresholds(
            org_id=caller["org_id"],
            product_id=product_id,
            thresholds=body.thresholds,
            updated_by=caller["uid"],
        )
    except LookupError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))


@router.delete("/products/{product_id}")
async def remove_product(product_id: str, caller=Depends(_admin)):
    removed = TierConfigService().remove_product(org_id=caller["org_id"], product_id=product_id)
    if not removed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not in tier config")
    return {"removed": True, "product_id": product_id}


# ══════════════════════════════════════════════════════════════════════════
# Tier 5 global thresholds
# ══════════════════════════════════════════════════════════════════════════

class Tier5Body(BaseModel):
    thresholds: dict


@router.get("/tier5")
async def get_tier5(caller=Depends(_admin)):
    """Get current Tier 5 global thresholds."""
    return TierConfigService().get_tier5(caller["org_id"])


@router.put("/tier5")
async def set_tier5(body: Tier5Body, caller=Depends(_admin)):
    """Replace Tier 5 global thresholds."""
    return TierConfigService().set_tier5(
        org_id=caller["org_id"],
        thresholds=body.thresholds,
        updated_by=caller["uid"],
    )
