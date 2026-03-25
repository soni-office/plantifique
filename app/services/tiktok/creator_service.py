from app.services.tiktok.client import TikTokClient
from app.core.config import settings
from app.agents.tools import TIER_MAP, TIER_3_THRESHOLDS, TIER_4_THRESHOLDS



SAMPLE_PATH = settings.creator_search_path


class TikTokCreatorService:

    @staticmethod
    def get_creator(access_token: str, shop_cipher: str, page_size: int,keyword: str | None = None):
        qs = {"page_size": page_size}
        body = {}
        if keyword:
            body["keyword"] = keyword


        res = TikTokClient.post(
            path=SAMPLE_PATH,
            access_token=access_token,
            shop_cipher=shop_cipher,
            qs=qs,
            body=body,
        )

        if isinstance(res, dict):
            res["internal_guidelines"] = {
                "product_tiers": TIER_MAP,
                "tier_3_thresholds": TIER_3_THRESHOLDS,
                "tier_4_thresholds": TIER_4_THRESHOLDS
            }

        return res

    @staticmethod
    def get_creator_detail(access_token: str, shop_cipher: str, creator_open_id: str):
        path = settings.creator_detail_path.format(creator_user_id=creator_open_id)
        
        res = TikTokClient.get(
            path=path,
            access_token=access_token,
            shop_cipher=shop_cipher,
            qs={},
        )

        if isinstance(res, dict):
            res["internal_guidelines"] = {
                "product_tiers": TIER_MAP,
                "tier_3_thresholds": TIER_3_THRESHOLDS,
                "tier_4_thresholds": TIER_4_THRESHOLDS
            }

        return res