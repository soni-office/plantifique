"""
Product search and detail — token management + caching + payload shaping.
"""
import logging
from functools import lru_cache

from app.clients.tiktok.product_client import TikTokProductClient
from app.services.token_service import get_token_service
from app.utils.shop_ciphers import shop_cipher
from app.cache import cache, keys, ttl

logger = logging.getLogger(__name__)


def shape_product(p: dict) -> dict:
    """Normalise a raw TikTok product dict into a UI-friendly card shape."""
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


class ProductService:

    def __init__(self):
        self.token_service = get_token_service()

    def _get_token_and_cipher(self, org_id: str) -> tuple[str, str]:
        access_token = self.token_service.get_valid_access_token(org_id)
        cipher = shop_cipher(org_id)["data"]["shops"][0]["cipher"]
        return access_token, cipher

    async def search(self, org_id: str, page_size: int = 20) -> dict:
        """Search shop products. Cached per org + page_size."""
        def _fetch():
            at, cipher = self._get_token_and_cipher(org_id)
            logger.info("Fetching product search from TikTok org=%s", org_id)
            return TikTokProductClient.search(
                access_token=at,
                shop_cipher=cipher,
                page_size=page_size,
            )

        return await cache.async_cache_or_fetch(
            keys.product_search(org_id, page_size),
            ttl.PRODUCT_SEARCH,
            _fetch,
        )

    async def get_detail(self, org_id: str, product_id: str) -> dict:
        """Fetch product detail. Cached per org + product_id."""
        def _fetch():
            at, cipher = self._get_token_and_cipher(org_id)
            logger.info("Fetching product detail product=%s org=%s", product_id, org_id)
            return TikTokProductClient.get_by_id(
                access_token=at,
                shop_cipher=cipher,
                product_id=product_id,
            )

        return await cache.async_cache_or_fetch(
            keys.product_detail(org_id, product_id),
            ttl.PRODUCT_DETAIL,
            _fetch,
        )

    async def get_shop_products_shaped(self, org_id: str, page_size: int = 50) -> list:
        """
        Fetch live shop products and return them in UI picker shape.
        Cached per org + page_size.
        """
        def _fetch():
            at, cipher = self._get_token_and_cipher(org_id)
            res = TikTokProductClient.search(
                access_token=at,
                shop_cipher=cipher,
                page_size=page_size,
            )
            raw = res.get("data", {}).get("products") or []
            return [shape_product(p) for p in raw]

        return await cache.async_cache_or_fetch(
            keys.shop_products(org_id, page_size),
            ttl.SHOP_PRODUCTS,
            _fetch,
        )


@lru_cache()
def get_product_service() -> "ProductService":
    return ProductService()
