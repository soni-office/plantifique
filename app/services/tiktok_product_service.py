import time
import requests
from app.config import settings


class TikTokProductService:
    BASE_URL = "https://open-api.tiktokglobalshop.com"

    @staticmethod
    def get_product(product_id: str, shop_cipher: str) -> dict:
        """
        Fetch product details from TikTok Shop Open API
        """

        endpoint = f"/product/202309/products/{product_id}"

        params = {
            "return_under_review_version": "true",
            "return_draft_version": "true",
            "locale": "en",
            "app_key": settings.TIKTOK_APP_KEY,
            "timestamp": int(time.time()),
            "shop_cipher": shop_cipher,
        }

        # 🔴 SIGN must be generated dynamically (placeholder here)
        params["sign"] = settings.generate_tiktok_sign(params)

        headers = {
            "x-tts-access-token": settings.TIKTOK_ACCESS_TOKEN,
            "content-type": "application/json",
        }

        response = requests.get(
            self.BASE_URL + endpoint,
            params=params,
            headers=headers,
            timeout=10,
        )

        response.raise_for_status()
        data = response.json()

        if data.get("code") != 0:
            raise Exception(f"TikTok API error: {data.get('message')}")

        return data["data"]
