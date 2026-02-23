from app.utils.shop_ciphers import shop_cipher
from fastapi import APIRouter, Query, Depends
from sqlalchemy.orm import Session
from app.services.product import product_search
from app.services.tiktokshop_oauth import get_valid_access_token
from app.db.database import get_db


router = APIRouter(prefix="/tiktok/products", tags=["TikTok Products"])

@router.get("/search")
def search_products(
    page_size: int = Query(20),
    db: Session = Depends(get_db)
):
    access_token = get_valid_access_token(db)
    res=shop_cipher(db)
    cipher = res["data"]["shops"][0]["cipher"]
    return product_search(access_token, cipher, page_size)
