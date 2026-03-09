from fastapi import APIRouter, Depends, Query
import logging

from app.api.auth_session import get_current_user
from app.services.tiktok.token_service import TokenService
from app.services.tiktok.sample_service import TikTokSampleService
from app.utils.shop_ciphers import shop_cipher

router = APIRouter(prefix="/tiktok/samples", tags=["TikTok Sample Requests"])

logger = logging.getLogger(__name__)


@router.get("/search")
async def search_sample_requests(
    page_size: int = Query(20),
    user=Depends(get_current_user),
):
    token_service = TokenService()
    access_token = token_service.get_valid_access_token(user["id"])
    res = shop_cipher(user["id"])
    cipher = res["data"]["shops"][0]["cipher"]
    logger.info("Searching sample requests for user=%s", user["id"])

    return TikTokSampleService.search(
        access_token=access_token,
        shop_cipher=cipher,
        page_size=page_size,
    )