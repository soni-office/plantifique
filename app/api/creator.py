import logging

from fastapi import APIRouter, Depends, Query

from app.api.auth_session import get_current_user
from app.services.tiktok.token_service import TokenService
from app.services.tiktok.creator_service import TikTokCreatorService
from app.utils.shop_ciphers import shop_cipher

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
    """Search marketplace creators. Calls TikTok API directly — no Firestore."""
    at, cipher = _tokens(user["org_id"])
    logger.info("Searching creators org=%s keyword=%s", user["org_id"], keyword)
    return TikTokCreatorService.search(
        access_token=at,
        shop_cipher=cipher,
        page_size=page_size,
        keyword=keyword,
    )


@router.get("/creators/{creator_open_id}")
def get_creator_detail(
    creator_open_id: str,
    user=Depends(get_current_user),
):
    """Fetch creator detail from TikTok API directly — no Firestore."""
    at, cipher = _tokens(user["org_id"])
    logger.info("Fetching creator detail creator=%s org=%s", creator_open_id, user["org_id"])
    return TikTokCreatorService.get_creator_detail(
        access_token=at,
        shop_cipher=cipher,
        creator_open_id=creator_open_id,
    )
