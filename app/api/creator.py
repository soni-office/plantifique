from fastapi import APIRouter, Depends, Query
import logging

from app.api.auth_session import get_current_user
from app.services.tiktok.token_service import TokenService
from app.services.tiktok.creator_service import TikTokCreatorService
from app.utils.shop_ciphers import shop_cipher

router = APIRouter(prefix="/tiktok/creators", tags=["TikTok Creator Profile"])

logger = logging.getLogger(__name__)


@router.get("/creators")
async def get_creators(
    page_size: int = Query(20),
    keyword: str | None = Query(None),
    user=Depends(get_current_user),
):
    token_service = TokenService()
    access_token = token_service.get_valid_access_token(user["id"])
    res = shop_cipher(user["id"])
    cipher = res["data"]["shops"][0]["cipher"]
    logger.info("Searching creators for user=%s", user["id"])
    
    return TikTokCreatorService.get_creator(
        access_token=access_token,
        shop_cipher=cipher,
        page_size=page_size,
        keyword=keyword,
    )

@router.get("/creators/{creator_open_id}")
async def get_creator_detail(
    creator_open_id: str,
    user=Depends(get_current_user),
):
    token_service = TokenService()
    access_token = token_service.get_valid_access_token(user["id"])
    res = shop_cipher(user["id"])
    cipher = res["data"]["shops"][0]["cipher"]
    logger.info("Fetching details for creator=%s user=%s", creator_open_id, user["id"])
    
    return TikTokCreatorService.get_creator_detail(
        access_token=access_token,
        shop_cipher=cipher,
        creator_open_id=creator_open_id
    )