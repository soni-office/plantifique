from fastapi import APIRouter, Depends, Query
import logging
from app.utils.shop_ciphers import shop_cipher
from app.api.auth_session import get_current_user
from app.services.tiktok.token_service import TokenService
from app.services.tiktok.product_service import TikTokProductService

router = APIRouter(prefix="/tiktok/products", tags=["TikTok Products"])

logger = logging.getLogger(__name__)


@router.get("/search")
async def search_products(
    page_size: int = Query(20),
    user=Depends(get_current_user),
):
    token_service = TokenService()
    access_token = token_service.get_valid_access_token(user["id"])

    res = shop_cipher(user["id"])
    cipher = res["data"]["shops"][0]["cipher"]

    logger.info("Searching products for user=%s", user["id"])

    return TikTokProductService.search(
        access_token=access_token,
        shop_cipher=cipher,
        page_size=page_size,
    )

@router.get("/{product_id}")
async def get_product(
    product_id: str,
    user=Depends(get_current_user),
):
    token_service = TokenService()
    access_token = token_service.get_valid_access_token(user["id"])

    res = shop_cipher(user["id"])
    cipher = res["data"]["shops"][0]["cipher"]

    logger.info("Fetching product=%s for user=%s", product_id, user["id"])

    return TikTokProductService.get_product_by_id(
        access_token=access_token,
        shop_cipher=cipher,
        product_id=product_id,
    )