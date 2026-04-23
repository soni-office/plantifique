"""
Creator search and detail — token management + caching.
"""
import logging
from functools import lru_cache
from typing import Optional

from app.clients.tiktok.creator_client import TikTokCreatorClient
from app.services.token_service import get_token_service
from app.utils.shop_ciphers import shop_cipher
from app.cache import cache, keys, ttl

logger = logging.getLogger(__name__)


class CreatorService:

    def __init__(self):
        self.token_service = get_token_service()

    def _get_token_and_cipher(self, org_id: str) -> tuple[str, str]:
        access_token = self.token_service.get_valid_access_token(org_id)
        cipher = shop_cipher(org_id)["data"]["shops"][0]["cipher"]
        return access_token, cipher

    async def search(
        self,
        org_id: str,
        keyword: Optional[str] = None,
        page_size: int = 20,
    ) -> dict:
        """Search marketplace creators. Cached per org + keyword + page_size."""
        def _fetch():
            at, cipher = self._get_token_and_cipher(org_id)
            logger.info("Fetching creator search from TikTok org=%s keyword=%s", org_id, keyword)
            return TikTokCreatorClient.search(
                access_token=at,
                shop_cipher=cipher,
                keyword=keyword,
                page_size=page_size,
            )

        return await cache.async_cache_or_fetch(
            keys.creator_search(org_id, keyword, page_size),
            ttl.CREATOR_SEARCH,
            _fetch,
        )

    async def get_detail(self, org_id: str, creator_open_id: str) -> dict:
        """Fetch creator detail. Cached per org + creator_open_id."""
        def _fetch():
            at, cipher = self._get_token_and_cipher(org_id)
            logger.info("Fetching creator detail creator=%s org=%s", creator_open_id, org_id)
            return TikTokCreatorClient.get_detail(
                access_token=at,
                shop_cipher=cipher,
                creator_open_id=creator_open_id,
            )

        return await cache.async_cache_or_fetch(
            keys.creator_detail(org_id, creator_open_id),
            ttl.CREATOR_DETAIL,
            _fetch,
        )


@lru_cache()
def get_creator_service() -> "CreatorService":
    return CreatorService()
