"""
Raw TikTok creator API calls.
"""
from app.clients.tiktok.base import TikTokClient
from app.core.config import settings


class TikTokCreatorClient:

    @staticmethod
    def search(
        access_token: str,
        shop_cipher: str,
        keyword: str | None = None,
        page_size: int = 20,
    ) -> dict:
        qs = {"page_size": page_size}
        body = {}
        if keyword:
            body["keyword"] = keyword
        return TikTokClient.post(
            path=settings.creator_search_path,
            access_token=access_token,
            shop_cipher=shop_cipher,
            qs=qs,
            body=body,
        )

    @staticmethod
    def get_detail(
        access_token: str,
        shop_cipher: str,
        creator_open_id: str,
    ) -> dict:
        path = settings.creator_detail_path.format(creator_user_id=creator_open_id)
        return TikTokClient.get(
            path=path,
            access_token=access_token,
            shop_cipher=shop_cipher,
            qs={},
        )
