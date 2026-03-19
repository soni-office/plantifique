from fastapi import APIRouter, Depends, Query
import logging

from app.api.auth_session import get_current_user
from app.services.tiktok.token_service import TokenService
from app.services.tiktok.creator_service import TikTokCreatorService
from app.repository.creator_repository import CreatorRepository
from app.utils.shop_ciphers import shop_cipher

router = APIRouter(prefix="/tiktok/creators", tags=["TikTok Creator Profile"])

logger = logging.getLogger(__name__)


@router.get("/creators")
async def get_creators(
    page_size: int = Query(20),
    keyword: str | None = Query(None),
    user=Depends(get_current_user),
):
    """Search for creators. Fetches from TikTok and caches results in Firestore."""
    token_service = TokenService()
    # Uses org-level token sharing
    access_token = token_service.get_valid_access_token(user["org_id"])
    
    res = shop_cipher(user["id"])
    cipher = res["data"]["shops"][0]["cipher"]
    
    logger.info("Searching creators for org=%s user=%s", user["org_id"], user["id"])
    
    tiktok_res = TikTokCreatorService.get_creator(
        access_token=access_token,
        shop_cipher=cipher,
        page_size=page_size,
        keyword=keyword,
    )

    # Cache search results to Firestore for O(1) auditability and speed
    repo = CreatorRepository()
    creators_list = tiktok_res.get("data", {}).get("creators", [])
    for creator in creators_list:
        repo.upsert(
            creator_id=creator.get("creator_id") or creator.get("id"),
            org_id=user["org_id"],
            data=creator
        )

    return tiktok_res


@router.get("/creators/{creator_open_id}")
async def get_creator_detail(
    creator_open_id: str,
    user=Depends(get_current_user),
):
    """
    Get creator detail. 
    Cache-first: Returns from Firestore if available, otherwise fetches from TikTok.
    """
    repo = CreatorRepository()
    
    # 1. Try Cache First (O(1))
    cached = repo.get(creator_open_id)
    if cached:
        logger.info("Serving creator=%s from Firestore cache", creator_open_id)
        return {"data": cached, "source": "cache"}

    # 2. Fetch from TikTok on Cache Miss
    token_service = TokenService()
    access_token = token_service.get_valid_access_token(user["org_id"])
    res = shop_cipher(user["id"])
    cipher = res["data"]["shops"][0]["cipher"]
    
    logger.info("Cache miss. Fetching details for creator=%s for org=%s", creator_open_id, user["org_id"])
    
    tiktok_res = TikTokCreatorService.get_creator_detail(
        access_token=access_token,
        shop_cipher=cipher,
        creator_open_id=creator_open_id
    )

    # 3. Update Cache
    creator_data = tiktok_res.get("data")
    if creator_data:
        repo.upsert(creator_id=creator_open_id, org_id=user["org_id"], data=creator_data)

    return tiktok_res