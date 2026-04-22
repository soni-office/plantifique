import logging

from fastapi import APIRouter, Depends, Query

from app.api.auth_session import get_current_user
from app.services.creator_service import CreatorService

router = APIRouter(prefix="/tiktok/creators", tags=["TikTok Creator Profile"])
logger = logging.getLogger(__name__)


@router.get("")
async def get_creators(
    page_size: int = Query(20),
    keyword: str | None = Query(None),
    user=Depends(get_current_user),
):
    """Search marketplace creators. Cached per org + keyword + page_size."""
    return await CreatorService().search(
        org_id=user["org_id"],
        keyword=keyword,
        page_size=page_size,
    )


@router.get("/{creator_open_id}")
async def get_creator_detail(
    creator_open_id: str,
    user=Depends(get_current_user),
):
    """Fetch creator detail. Cached per org + creator_open_id."""
    return await CreatorService().get_detail(
        org_id=user["org_id"],
        creator_open_id=creator_open_id,
    )
