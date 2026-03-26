

from app.services.tiktok.client import TikTokClient
from app.core.config import settings
from app.mock.sample_mock_data import get_mock_sample_requests

SAMPLE_PATH = "/affiliate_seller/202508/sample_applications/search"


class TikTokSampleService:

    @staticmethod
    def search(access_token: str, shop_cipher: str, page_size: int):
        if settings.mock_sample_requests:
            return get_mock_sample_requests()
    
        qs = {"page_size": page_size}
        body = {}
        print("inside service tiktok sample service")
        # breakpoint()
        return TikTokClient.post(
            path=SAMPLE_PATH,
            access_token=access_token,
            shop_cipher=shop_cipher,
            qs=qs,
            body=body,
        )