from app.services.tiktok.client import TikTokClient

SAMPLE_PATH = "/affiliate_seller/202508/sample_applications/search"


class TikTokSampleService:

    @staticmethod
    def search(
        access_token: str,
        shop_cipher: str,
        page_size: int = 30,
        page_token: str | None = None,
        status: str = "PENDING",
    ) -> dict:
        """
        Fetch one page of sample applications from TikTok.
        Returns the raw TikTok response dict:
          { code, data: { sample_applications: [...], next_page_token: "..." } }
        """
        qs = {"page_size": page_size}
        body: dict = {"status": status}
        if page_token:
            body["page_token"] = page_token

        return TikTokClient.post(
            path=SAMPLE_PATH,
            access_token=access_token,
            shop_cipher=shop_cipher,
            qs=qs,
            body=body,
        )
