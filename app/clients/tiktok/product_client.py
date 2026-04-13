"""
Raw TikTok product API calls.
"""
from app.clients.tiktok.base import TikTokClient

_PRODUCT_SEARCH_PATH = "/product/202502/products/search"
_PRODUCT_DETAIL_PATH = "/product/202309/products/{product_id}"


class TikTokProductClient:

    @staticmethod
    def search(access_token: str, shop_cipher: str, page_size: int = 20) -> dict:
        return TikTokClient.post(
            path=_PRODUCT_SEARCH_PATH,
            access_token=access_token,
            shop_cipher=shop_cipher,
            qs={"page_size": page_size},
            body={"status": "ACTIVATE"},
        )

    @staticmethod
    def get_by_id(access_token: str, shop_cipher: str, product_id: str) -> dict:
        path = _PRODUCT_DETAIL_PATH.format(product_id=product_id)
        return TikTokClient.get(
            path=path,
            access_token=access_token,
            shop_cipher=shop_cipher,
            qs={},
        )
