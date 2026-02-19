from fastapi import APIRouter, Query, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.sample_request import sample_request
from app.services.tiktokshop_oauth import get_valid_access_token

router = APIRouter(prefix="/tiktok/sample_request", tags=["Sample Requests"])

@router.get("/search")
def search_products(
    shop_cipher: str = Query(...),
    page_size: int = Query(20),
    db: Session = Depends(get_db)
):
    access_token = get_valid_access_token(db)

    return sample_request(access_token, shop_cipher, page_size)
