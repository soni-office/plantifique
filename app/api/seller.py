from fastapi import APIRouter
from app.services.product_context_service import get_product_context

router = APIRouter()

@router.get("/product/{product_id}")
def get_product(product_id: str, shop_cipher: str):
    return get_product_context(product_id, shop_cipher)
