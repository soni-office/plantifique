from app.schema.product_schema import ProductSchema
from app.services.tiktok_product_service import TikTokProductService


def get_product_context(product_id: str, shop_cipher: str) -> ProductSchema:
    raw = TikTokProductService.get_product(product_id, shop_cipher)

    return ProductSchema(
        id=raw["id"],
        title=raw["title"],
        status=raw["status"],
        category_id=raw["category_chains"][0]["id"]
        if raw.get("category_chains")
        else None,
        brand_name=raw["brand"]["name"] if raw.get("brand") else None,
        price=float(raw["skus"][0]["price"]["sale_price"])
        if raw.get("skus")
        else None,
    )
