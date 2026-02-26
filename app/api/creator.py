
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
import logging

from app.db.database import get_db
from app.api.auth_session import get_current_user
from app.services.tiktok.token_service import TokenService
from app.services.tiktok.creator_service import TikTokCreatorService
from app.utils.shop_ciphers import shop_cipher
router = APIRouter(prefix="/tiktok/creators", tags=["TikTok Creator Profile"])

logger = logging.getLogger(__name__)


@router.get("/creators")
async def get_creators(
    page_size: int = Query(20),
    db: Session = Depends(get_db),
    keyword: str | None = Query(None),
    user=Depends(get_current_user),
):
    token_service = TokenService(db)
    access_token = token_service.get_valid_access_token(user.id)
    print("Got access token for user_id=", user.id, " token=", access_token)
    res = shop_cipher(db,user.id) 
    print("sdfsdfgfdg", res)
    cipher = res["data"]["shops"][0]["cipher"] # Or fetch properly from DB
    print("Using shop_cipher=", cipher, " for user_id=", user.id)
    logger.info("Searching creators for user=%s", user.id)

    return TikTokCreatorService.get_creator(
        access_token=access_token,
        shop_cipher=cipher,
        page_size=page_size,
        keyword=keyword,
    )