import logging

from fastapi import APIRouter, Depends, Query

from app.api.auth_session import get_current_user
from app.services.tiktok.token_service import TokenService
from app.services.tiktok.product_service import TikTokProductService
from app.utils.shop_ciphers import shop_cipher
from app.cache import cache, keys, ttl

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
    """Search shop products. Cached per org + page_size."""
    org_id = user["org_id"]

    def _fetch():
        at, cipher = _tokens(org_id)
        logger.info("Fetching product search from TikTok org=%s", org_id)
        return TikTokProductService.search(
            access_token=at,
            shop_cipher=cipher,
            page_size=page_size,
        )

    return cache.cache_or_fetch(
        keys.product_search(org_id, page_size),
        ttl.PRODUCT_SEARCH,
        _fetch,
    )


@router.get("/{product_id}")
async def get_product(
    product_id: str,
    user=Depends(get_current_user),
):
    """Fetch product detail. Cached per org + product_id."""
    org_id = user["org_id"]

    def _fetch():
        at, cipher = _tokens(org_id)
        logger.info("Fetching product detail product=%s org=%s", product_id, org_id)
        return TikTokProductService.get_product_by_id(
            access_token=at,
            shop_cipher=cipher,
            product_id=product_id,
        )

    return cache.cache_or_fetch(
        keys.product_detail(org_id, product_id),
        ttl.PRODUCT_DETAIL,
        _fetch,
    )
