"""
Raw TikTok sample application API calls.
"""
from app.clients.tiktok.base import TikTokClient

_SAMPLE_PATH = "/affiliate_seller/202508/sample_applications/search"

# Version from official TikTok docs: 202507
REVIEW_PATH = "/affiliate_seller/202507/sample_applications/{application_id}/review"


class TikTokSampleClient:

    @staticmethod
    def search(
        access_token: str,
        shop_cipher: str,
        page_size: int = 30,
        page_token: str | None = None,
        status: str = "PENDING",
        **extra_filters
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

    @staticmethod
    def review(
        access_token: str,
        shop_cipher: str,
        application_id: str,
        review_result: str,
        reject_reason: str | None = None,
    ) -> dict:
        """
        Approve or reject a creator's sample application on TikTok Shop.

        Based on official TikTok docs:
          POST /affiliate_seller/202507/sample_applications/{application_id}/review

        Args:
            access_token:   Seller access token.
            shop_cipher:    Shop cipher from Get Authorization Shop.
            application_id: The sample application ID (goes in the URL path).
            review_result:  "APPROVE" or "REJECT".
            reject_reason:  Required when review_result is "REJECT".
                            One of: NOT_MATCH | OFFLINE | OUT_OF_STOCK | OTHER
        """
        if review_result not in ("APPROVE", "REJECT"):
            raise ValueError(f"Invalid review_result '{review_result}'. Must be 'APPROVE' or 'REJECT'.")

        if review_result == "REJECT" and not reject_reason:
            raise ValueError("reject_reason is required when review_result is 'REJECT'.")

        valid_reject_reasons = {"NOT_MATCH", "OFFLINE", "OUT_OF_STOCK", "OTHER"}
        if reject_reason and reject_reason not in valid_reject_reasons:
            raise ValueError(
                f"Invalid reject_reason '{reject_reason}'. "
                f"Must be one of: {', '.join(valid_reject_reasons)}"
            )

        path = REVIEW_PATH.format(application_id=application_id)
        body: dict = {"review_result": review_result}
        if reject_reason:
            body["reject_reason"] = reject_reason

        return TikTokClient.post(
            path=path,
            access_token=access_token,
            shop_cipher=shop_cipher,
            qs={},
            body=body,
        )
