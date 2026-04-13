"""
Raw TikTok sample application API calls.
"""
from app.clients.tiktok.base import TikTokClient

_SAMPLE_PATH = "/affiliate_seller/202508/sample_applications/search"


class TikTokSampleClient:

    @staticmethod
    def search(
        access_token: str,
        shop_cipher: str,
        page_size: int = 30,
        page_token: str | None = None,
        status: str = "PENDING",
    ) -> dict:
        """
        Fetch one page of sample applications.
        Returns raw TikTok response:
          { code, data: { sample_applications: [...], next_page_token: "..." } }
        """
        body: dict = {"status": status}
        qs: dict = {"page_size": page_size}
        if page_token:
            qs["page_token"] = page_token
        return TikTokClient.post(
            path=_SAMPLE_PATH,
            access_token=access_token,
            shop_cipher=shop_cipher,
            qs=qs,
            body=body,
        )
