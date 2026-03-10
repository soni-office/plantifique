from app.services.tiktok.client import TikTokClient
PRODUCT_PATH = "/product/202502/products/search"
PRODUCT_DETAIL_PATH = "/product/202309/products/{product_id}"

class TikTokProductService:

    @staticmethod
    def search(access_token: str, shop_cipher: str, page_size: int):

        qs = {"page_size": page_size}
        body = {"status": "ALL"}

        return TikTokClient.post(
            path=PRODUCT_PATH,
            access_token=access_token,
            shop_cipher=shop_cipher,
            qs=qs,
            body=body,
        )

    @staticmethod
    def get_product_by_id(access_token: str, shop_cipher: str, product_id: str):
        
        path = PRODUCT_DETAIL_PATH.format(product_id=product_id)
        qs = {}

        return TikTokClient.get(
            path=path,
            access_token=access_token,
            shop_cipher=shop_cipher,
            qs=qs,
        )
