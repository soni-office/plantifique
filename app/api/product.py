

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
import logging
from app.utils.shop_ciphers import shop_cipher
from app.db.database import get_db
from app.api.auth_session import get_current_user
from app.services.tiktok.token_service import TokenService
from app.services.tiktok.product_service import TikTokProductService

router = APIRouter(prefix="/tiktok/products", tags=["TikTok Products"])

logger = logging.getLogger(__name__)


@router.get("/search")
async def search_products(
    page_size: int = Query(20),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    token_service = TokenService(db)
    access_token = token_service.get_valid_access_token(user.id)

    # For now assume shop_cipher stored in DB
    res = shop_cipher(db,user.id) 
    # breakpoint()
    cipher = res["data"]["shops"][0]["cipher"]

    logger.info("Searching products for user=%s", user.id)

    return TikTokProductService.search(
        access_token=access_token,
        shop_cipher=cipher,
        page_size=page_size,
    )