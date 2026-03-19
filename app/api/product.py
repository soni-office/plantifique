from fastapi import APIRouter, Depends, Query
import logging

from app.api.auth_session import get_current_user
from app.services.tiktok.token_service import TokenService
from app.services.tiktok.product_service import TikTokProductService
from app.repository.product_repository import ProductRepository
from app.utils.shop_ciphers import shop_cipher

router = APIRouter(prefix="/tiktok/products", tags=["TikTok Products"])

logger = logging.getLogger(__name__)


@router.get("/search")
async def search_products(
    page_size: int = Query(20),
    user=Depends(get_current_user),
):
    """Search for products. Use shared org-level tokens and cache to Firestore."""
    token_service = TokenService()
    # Sharing org-level credentials
    access_token = token_service.get_valid_access_token(user["org_id"])

    res = shop_cipher(user["id"])
    cipher = res["data"]["shops"][0]["cipher"]

    logger.info("Searching products for org=%s user=%s", user["org_id"], user["id"])

    tiktok_res = TikTokProductService.search(
        access_token=access_token,
        shop_cipher=cipher,
        page_size=page_size,
    )

    # Caching Layer (O(1) persistence)
    repo = ProductRepository()
    products_list = tiktok_res.get("data", {}).get("products", [])
    for prod in products_list:
        repo.upsert(
            product_id=prod["id"],
            org_id=user["org_id"],
            data=prod
        )

    return tiktok_res


@router.get("/{product_id}")
async def get_product(
    product_id: str,
    user=Depends(get_current_user),
):
    """
    Get product details. 
    Cache-First: Serve from Firestore if cached, otherwise hit TikTok API.
    """
    repo = ProductRepository()
    
    # 1. Cache First
    cached = repo.get(product_id)
    if cached:
        logger.info("Serving product=%s from Firestore cache", product_id)
        return {"data": cached, "source": "cache"}

    # 2. API on Cache Miss
    token_service = TokenService()
    access_token = token_service.get_valid_access_token(user["org_id"])
    res = shop_cipher(user["id"])
    cipher = res["data"]["shops"][0]["cipher"]

    logger.info("Cache miss. Fetching details for product=%s for org=%s", product_id, user["org_id"])

    tiktok_res = TikTokProductService.get_product_by_id(
        access_token=access_token,
        shop_cipher=cipher,
        product_id=product_id,
    )

    # 3. Cache Update
    product_data = tiktok_res.get("data")
    if product_data:
        repo.upsert(product_id=product_id, org_id=user["org_id"], data=product_data)

    return tiktok_res