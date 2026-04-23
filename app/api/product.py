import logging

from fastapi import APIRouter, Depends, Query

from app.api.auth_session import get_current_user
from app.services.product_service import ProductService, get_product_service

router = APIRouter(prefix="/tiktok/products", tags=["TikTok Products"])
logger = logging.getLogger(__name__)


@router.get("/search")
async def search_products(
    page_size: int = Query(20),
    user=Depends(get_current_user),
    svc: ProductService = Depends(get_product_service),
):
    """Search shop products. Cached per org + page_size."""
    return await svc.search(
        org_id=user["org_id"],
        page_size=page_size,
    )


@router.get("/{product_id}")
async def get_product(
    product_id: str,
    user=Depends(get_current_user),
    svc: ProductService = Depends(get_product_service),
):
    """Fetch product detail. Cached per org + product_id."""
    return await svc.get_detail(
        org_id=user["org_id"],
        product_id=product_id,
    )
