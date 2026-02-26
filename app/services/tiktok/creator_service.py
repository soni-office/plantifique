

from app.services.tiktok.client import TikTokClient
from app.core.config import settings


SAMPLE_PATH = "/affiliate_seller/202406/marketplace_creators/search"


class TikTokCreatorService:

    @staticmethod
    def get_creator(access_token: str, shop_cipher: str, page_size: int,keyword: str | None = None):
        qs = {"page_size": page_size}
        body = {}
        if keyword:
            body["keyword"] = keyword
        print("inside service tiktok creator service")
        # breakpoint()
        return TikTokClient.post(
            path=SAMPLE_PATH,
            access_token=access_token,
            shop_cipher=shop_cipher,
            qs=qs,
            body=body,
        )