from app.services.tiktok.client import TikTokClient
from app.core.config import settings
from app.mock.sample_mock_data import get_mock_sample_requests

PRODUCT_SEARCH_PATH = "/product/202309/products/search"
PRODUCT_DETAIL_PATH = "/product/202309/products/{product_id}"


def _build_mock_product_lookup() -> dict:
    """
    Build a product_id → full ProductDetails dict from the mock sample requests.
    Fields match the frontend's ProductDetails TypeScript interface exactly.
    """
    # Rich mock product details keyed by product ID
    _PRODUCT_DETAILS = {
        "PROD_T3_001": {
            "id": "PROD_T3_001",
            "title": "Peach Foot Mask",
            "description": "<p>A gentle exfoliating foot mask infused with real peach extract. Softens rough, dry skin overnight for baby-smooth feet.</p>",
            "status": "ACTIVE",
            "product_status": "FOR_SALE",
            "listing_quality_tier": "GOOD",
            "create_time": 1740000000,
            "update_time": 1772700000,
            "brand": {"id": "BRAND_001", "name": "Glow Beauty US"},
            "category_chains": [
                {"id": "CAT_001", "local_name": "Beauty & Personal Care", "parent_id": "", "is_leaf": False},
                {"id": "CAT_002", "local_name": "Foot Care", "parent_id": "CAT_001", "is_leaf": True},
            ],
            "audit": {"status": "APPROVED", "pre_approved_reasons": []},
            "package_dimensions": {"length": "15", "width": "10", "height": "3", "unit": "cm"},
            "package_weight": {"value": "120", "unit": "g"},
            "main_images": [{"urls": ["https://picsum.photos/seed/PROD_T3_001/400/400"], "thumb_urls": ["https://picsum.photos/seed/PROD_T3_001/128/128"]}],
            "skus": [
                {
                    "id": "SKU_T3_001",
                    "seller_sku": "PFM-PEACH-ONE-SIZE",
                    "price": {"currency": "USD", "sale_price": "14.99", "tax_exclusive_price": "13.50"},
                    "status_info": {"status": "ACTIVE"},
                }
            ],
            "product_attributes": [
                {"id": "ATTR_001", "name": "Skin Type", "values": [{"id": "V1", "name": "All Skin Types"}]},
                {"id": "ATTR_002", "name": "Scent", "values": [{"id": "V2", "name": "Peach"}]},
                {"id": "ATTR_003", "name": "Form", "values": [{"id": "V3", "name": "Mask"}]},
            ],
        },
        "PROD_T3_002": {
            "id": "PROD_T3_002",
            "title": "Marine Clay Mask",
            "description": "<p>Deep-cleansing marine clay mask that draws out impurities and tightens pores. Leaves skin refreshed and detoxified.</p>",
            "status": "ACTIVE",
            "product_status": "FOR_SALE",
            "listing_quality_tier": "EXCELLENT",
            "create_time": 1740100000,
            "update_time": 1772710000,
            "brand": {"id": "BRAND_001", "name": "Glow Beauty US"},
            "category_chains": [
                {"id": "CAT_001", "local_name": "Beauty & Personal Care", "parent_id": "", "is_leaf": False},
                {"id": "CAT_003", "local_name": "Face Masks", "parent_id": "CAT_001", "is_leaf": True},
            ],
            "audit": {"status": "APPROVED", "pre_approved_reasons": []},
            "package_dimensions": {"length": "12", "width": "8", "height": "4", "unit": "cm"},
            "package_weight": {"value": "200", "unit": "g"},
            "main_images": [{"urls": ["https://picsum.photos/seed/PROD_T3_002/400/400"], "thumb_urls": ["https://picsum.photos/seed/PROD_T3_002/128/128"]}],
            "skus": [
                {
                    "id": "SKU_T3_002",
                    "seller_sku": "MCM-CLAY-100G",
                    "price": {"currency": "USD", "sale_price": "19.99", "tax_exclusive_price": "17.99"},
                    "status_info": {"status": "ACTIVE"},
                }
            ],
            "product_attributes": [
                {"id": "ATTR_001", "name": "Skin Type", "values": [{"id": "V1", "name": "Oily"}, {"id": "V4", "name": "Combination"}]},
                {"id": "ATTR_002", "name": "Key Ingredient", "values": [{"id": "V5", "name": "Marine Clay"}]},
            ],
        },
        "PROD_T3_003": {
            "id": "PROD_T3_003",
            "title": "Natural Jade Roller",
            "description": "<p>Authentic natural jade facial roller to reduce puffiness, boost circulation and enhance product absorption.</p>",
            "status": "ACTIVE",
            "product_status": "FOR_SALE",
            "listing_quality_tier": "GOOD",
            "create_time": 1740200000,
            "update_time": 1772720000,
            "brand": {"id": "BRAND_001", "name": "Glow Beauty US"},
            "category_chains": [
                {"id": "CAT_001", "local_name": "Beauty & Personal Care", "parent_id": "", "is_leaf": False},
                {"id": "CAT_004", "local_name": "Facial Tools", "parent_id": "CAT_001", "is_leaf": True},
            ],
            "audit": {"status": "APPROVED", "pre_approved_reasons": []},
            "package_dimensions": {"length": "18", "width": "6", "height": "3", "unit": "cm"},
            "package_weight": {"value": "95", "unit": "g"},
            "main_images": [{"urls": ["https://picsum.photos/seed/PROD_T3_003/400/400"], "thumb_urls": ["https://picsum.photos/seed/PROD_T3_003/128/128"]}],
            "skus": [
                {
                    "id": "SKU_T3_003",
                    "seller_sku": "NJR-JADE-STD",
                    "price": {"currency": "USD", "sale_price": "24.99", "tax_exclusive_price": "22.50"},
                    "status_info": {"status": "ACTIVE"},
                }
            ],
            "product_attributes": [
                {"id": "ATTR_001", "name": "Material", "values": [{"id": "V6", "name": "Jade"}]},
                {"id": "ATTR_002", "name": "Use", "values": [{"id": "V7", "name": "Face Massage"}]},
            ],
        },
        "PROD_T4_001": {
            "id": "PROD_T4_001",
            "title": "Mango Cleansing Balm",
            "description": "<p>Luxurious mango-butter cleansing balm that melts away makeup, SPF and impurities without stripping skin.</p>",
            "status": "ACTIVE",
            "product_status": "FOR_SALE",
            "listing_quality_tier": "GOOD",
            "create_time": 1740300000,
            "update_time": 1772730000,
            "brand": {"id": "BRAND_001", "name": "Glow Beauty US"},
            "category_chains": [
                {"id": "CAT_001", "local_name": "Beauty & Personal Care", "parent_id": "", "is_leaf": False},
                {"id": "CAT_005", "local_name": "Cleansers", "parent_id": "CAT_001", "is_leaf": True},
            ],
            "audit": {"status": "APPROVED", "pre_approved_reasons": []},
            "package_dimensions": {"length": "10", "width": "10", "height": "5", "unit": "cm"},
            "package_weight": {"value": "150", "unit": "g"},
            "main_images": [{"urls": ["https://picsum.photos/seed/PROD_T4_001/400/400"], "thumb_urls": ["https://picsum.photos/seed/PROD_T4_001/128/128"]}],
            "skus": [
                {
                    "id": "SKU_T4_001",
                    "seller_sku": "MCB-MANGO-90G",
                    "price": {"currency": "USD", "sale_price": "22.00", "tax_exclusive_price": "20.00"},
                    "status_info": {"status": "ACTIVE"},
                }
            ],
            "product_attributes": [
                {"id": "ATTR_001", "name": "Skin Type", "values": [{"id": "V1", "name": "All Skin Types"}]},
                {"id": "ATTR_002", "name": "Key Ingredient", "values": [{"id": "V8", "name": "Mango Butter"}]},
            ],
        },
        "PROD_T4_002": {
            "id": "PROD_T4_002",
            "title": "Kojic Acid Bar Soap",
            "description": "<p>Brightening kojic acid bar soap that targets dark spots, hyperpigmentation and uneven skin tone for a luminous complexion.</p>",
            "status": "ACTIVE",
            "product_status": "FOR_SALE",
            "listing_quality_tier": "EXCELLENT",
            "create_time": 1740400000,
            "update_time": 1772740000,
            "brand": {"id": "BRAND_001", "name": "Glow Beauty US"},
            "category_chains": [
                {"id": "CAT_001", "local_name": "Beauty & Personal Care", "parent_id": "", "is_leaf": False},
                {"id": "CAT_006", "local_name": "Body Wash & Soap", "parent_id": "CAT_001", "is_leaf": True},
            ],
            "audit": {"status": "APPROVED", "pre_approved_reasons": []},
            "package_dimensions": {"length": "9", "width": "6", "height": "3", "unit": "cm"},
            "package_weight": {"value": "135", "unit": "g"},
            "main_images": [{"urls": ["https://picsum.photos/seed/PROD_T4_002/400/400"], "thumb_urls": ["https://picsum.photos/seed/PROD_T4_002/128/128"]}],
            "skus": [
                {
                    "id": "SKU_T4_002",
                    "seller_sku": "KAS-KOJIC-135G",
                    "price": {"currency": "USD", "sale_price": "12.99", "tax_exclusive_price": "11.75"},
                    "status_info": {"status": "ACTIVE"},
                }
            ],
            "product_attributes": [
                {"id": "ATTR_001", "name": "Skin Concern", "values": [{"id": "V9", "name": "Dark Spots"}, {"id": "V10", "name": "Hyperpigmentation"}]},
                {"id": "ATTR_002", "name": "Key Ingredient", "values": [{"id": "V11", "name": "Kojic Acid"}]},
            ],
        },
        "PROD_T1_001": {
            "id": "PROD_T1_001",
            "title": "V-Line Sculpting Mask",
            "description": "<p>Innovative V-line lift and sculpting mask that contours your jawline and chin for a defined, slimmer appearance.</p>",
            "status": "ACTIVE",
            "product_status": "FOR_SALE",
            "listing_quality_tier": "EXCELLENT",
            "create_time": 1740500000,
            "update_time": 1772750000,
            "brand": {"id": "BRAND_001", "name": "Glow Beauty US"},
            "category_chains": [
                {"id": "CAT_001", "local_name": "Beauty & Personal Care", "parent_id": "", "is_leaf": False},
                {"id": "CAT_003", "local_name": "Face Masks", "parent_id": "CAT_001", "is_leaf": True},
            ],
            "audit": {"status": "APPROVED", "pre_approved_reasons": []},
            "package_dimensions": {"length": "20", "width": "15", "height": "1", "unit": "cm"},
            "package_weight": {"value": "45", "unit": "g"},
            "main_images": [{"urls": ["https://picsum.photos/seed/PROD_T1_001/400/400"], "thumb_urls": ["https://picsum.photos/seed/PROD_T1_001/128/128"]}],
            "skus": [
                {
                    "id": "SKU_T1_001",
                    "seller_sku": "VLS-VLINE-5PK",
                    "price": {"currency": "USD", "sale_price": "29.99", "tax_exclusive_price": "27.00"},
                    "status_info": {"status": "ACTIVE"},
                }
            ],
            "product_attributes": [
                {"id": "ATTR_001", "name": "Skin Concern", "values": [{"id": "V12", "name": "Face Contouring"}]},
                {"id": "ATTR_002", "name": "Pack Size", "values": [{"id": "V13", "name": "5 Masks"}]},
            ],
        },
        "PROD_T2_001": {
            "id": "PROD_T2_001",
            "title": "Brightening Exfoliating Pads",
            "description": "<p>Pre-soaked exfoliating pads with AHA/BHA blend and niacinamide to resurface, brighten and even skin tone with every swipe.</p>",
            "status": "ACTIVE",
            "product_status": "FOR_SALE",
            "listing_quality_tier": "GOOD",
            "create_time": 1740600000,
            "update_time": 1772760000,
            "brand": {"id": "BRAND_001", "name": "Glow Beauty US"},
            "category_chains": [
                {"id": "CAT_001", "local_name": "Beauty & Personal Care", "parent_id": "", "is_leaf": False},
                {"id": "CAT_007", "local_name": "Exfoliants", "parent_id": "CAT_001", "is_leaf": True},
            ],
            "audit": {"status": "APPROVED", "pre_approved_reasons": []},
            "package_dimensions": {"length": "11", "width": "11", "height": "4", "unit": "cm"},
            "package_weight": {"value": "180", "unit": "g"},
            "main_images": [{"urls": ["https://picsum.photos/seed/PROD_T2_001/400/400"], "thumb_urls": ["https://picsum.photos/seed/PROD_T2_001/128/128"]}],
            "skus": [
                {
                    "id": "SKU_T2_001",
                    "seller_sku": "BEP-BRIGHT-60CT",
                    "price": {"currency": "USD", "sale_price": "17.99", "tax_exclusive_price": "16.20"},
                    "status_info": {"status": "ACTIVE"},
                }
            ],
            "product_attributes": [
                {"id": "ATTR_001", "name": "Key Ingredient", "values": [{"id": "V14", "name": "AHA/BHA"}, {"id": "V15", "name": "Niacinamide"}]},
                {"id": "ATTR_002", "name": "Count", "values": [{"id": "V16", "name": "60 Pads"}]},
            ],
        },
    }

    return _PRODUCT_DETAILS


# Build the mock lookup once at module load time
_MOCK_PRODUCT_LOOKUP = _build_mock_product_lookup()


class TikTokProductService:

    @staticmethod
    def search(access_token: str, shop_cipher: str, page_size: int):
        if settings.mock_tiktok:
            # Collect all unique products from mock sample data
            products = list(_MOCK_PRODUCT_LOOKUP.values())
            return {
                "code": 0,
                "message": "Success",
                "data": {
                    "products": products[:page_size],
                    "total_count": len(products),
                },
            }

        qs = {"page_size": page_size}
        body = {}

        return TikTokClient.post(
            path=PRODUCT_SEARCH_PATH,
            access_token=access_token,
            shop_cipher=shop_cipher,
            qs=qs,
            body=body,
        )

    @staticmethod
    def get_product_by_id(access_token: str, shop_cipher: str, product_id: str):
        if settings.mock_tiktok:
            product = _MOCK_PRODUCT_LOOKUP.get(product_id)
            if product:
                return product
            # Return a structured 404-style mock response instead of crashing
            return {
                "code": 404,
                "message": f"Mock product '{product_id}' not found",
                "data": {},
            }

        path = PRODUCT_DETAIL_PATH.format(product_id=product_id)
        qs = {}

        return TikTokClient.get(
            path=path,
            access_token=access_token,
            shop_cipher=shop_cipher,
            qs=qs,
        )
