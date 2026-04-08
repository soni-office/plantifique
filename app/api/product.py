import logging

from fastapi import APIRouter, Depends, Query

from app.api.auth_session import get_current_user
from app.services.tiktok.token_service import TokenService
from app.services.tiktok.product_service import TikTokProductService
from app.utils.shop_ciphers import shop_cipher

router = APIRouter(prefix="/tiktok/products", tags=["TikTok Products"])
logger = logging.getLogger(__name__)


def _tokens(org_id: str) -> tuple[str, str]:
    at = TokenService().get_valid_access_token(org_id)
    cipher = shop_cipher(org_id)["data"]["shops"][0]["cipher"]
    return at, cipher


@router.get("/search")
async def search_products(
    page_size: int = Query(20),
    user=Depends(get_current_user),
):
    """Search shop products. Calls TikTok API directly — no Firestore."""
    at, cipher = _tokens(user["org_id"])
    logger.info("Searching products org=%s", user["org_id"])
    return TikTokProductService.search(
        access_token=at,
        shop_cipher=cipher,
        page_size=page_size,
    )


@router.get("/{product_id}")
async def get_product(
    product_id: str,
    user=Depends(get_current_user),
):
    """Fetch product detail from TikTok API directly — no Firestore."""
    at, cipher = _tokens(user["org_id"])
    logger.info("Fetching product detail product=%s org=%s", product_id, user["org_id"])
    return TikTokProductService.get_product_by_id(
        access_token=at,
        shop_cipher=cipher,
        product_id=product_id,
    )
