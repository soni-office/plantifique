from app.services.tiktok.client import TikTokClient
from app.core.config import settings

CREATOR_SEARCH_PATH = settings.creator_search_path


class TikTokCreatorService:

    @staticmethod
    def search(access_token: str, shop_cipher: str, keyword: str | None = None, page_size: int = 20):
        qs = {"page_size": page_size}
        body = {}
        if keyword:
            body["keyword"] = keyword

        return TikTokClient.post(
            path=CREATOR_SEARCH_PATH,
            access_token=access_token,
            shop_cipher=shop_cipher,
            qs=qs,
            body=body,
        )

    # Keep old name as alias so existing callers (agent, api/creator.py) don't break
    get_creator = search

    @staticmethod
    def get_creator_detail(access_token: str, shop_cipher: str, creator_open_id: str):
        path = settings.creator_detail_path.format(creator_user_id=creator_open_id)
        return TikTokClient.get(
            path=path,
            access_token=access_token,
            shop_cipher=shop_cipher,
            qs={},
        )
