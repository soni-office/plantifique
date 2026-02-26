from app.services.tiktok.client import TikTokClient

PRODUCT_PATH = "/product/202309/products/search"


class TikTokProductService:

    @staticmethod
    def search(access_token: str, shop_cipher: str, page_size: int):

        qs = {"page_size": page_size}
        body = {}

        return TikTokClient.post(
            path=PRODUCT_PATH,
            access_token=access_token,
            shop_cipher=shop_cipher,
            qs=qs,
            body=body,
        )
