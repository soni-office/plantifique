import logging

from fastapi import APIRouter, Depends, Query

from app.api.auth_session import get_current_user
from app.services.tiktok.token_service import TokenService
from app.services.tiktok.creator_service import TikTokCreatorService
from app.utils.shop_ciphers import shop_cipher
from app.cache import cache, keys, ttl

router = APIRouter(prefix="/tiktok/creators", tags=["TikTok Creator Profile"])
logger = logging.getLogger(__name__)


def _tokens(org_id: str) -> tuple[str, str]:
    at = TokenService().get_valid_access_token(org_id)
    cipher = shop_cipher(org_id)["data"]["shops"][0]["cipher"]
    return at, cipher


@router.get("/creators")
async def get_creators(
    page_size: int = Query(20),
    keyword: str | None = Query(None),
    user=Depends(get_current_user),
):
    """Search marketplace creators. Cached per org + keyword + page_size."""
    org_id = user["org_id"]

    def _fetch():
        at, cipher = _tokens(org_id)
        logger.info("Fetching creator search from TikTok org=%s keyword=%s", org_id, keyword)
        return TikTokCreatorService.search(
            access_token=at,
            shop_cipher=cipher,
            page_size=page_size,
            keyword=keyword,
        )

    return cache.cache_or_fetch(
        keys.creator_search(org_id, keyword, page_size),
        ttl.CREATOR_SEARCH,
        _fetch,
    )


@router.get("/creators/{creator_open_id}")
def get_creator_detail(
    creator_open_id: str,
    user=Depends(get_current_user),
):
    """Fetch creator detail. Cached per org + creator_open_id."""
    org_id = user["org_id"]

    def _fetch():
        at, cipher = _tokens(org_id)
        logger.info("Fetching creator detail creator=%s org=%s", creator_open_id, org_id)
        return TikTokCreatorService.get_creator_detail(
            access_token=at,
            shop_cipher=cipher,
            creator_open_id=creator_open_id,
        )

    return cache.cache_or_fetch(
        keys.creator_detail(org_id, creator_open_id),
        ttl.CREATOR_DETAIL,
        _fetch,
    )
