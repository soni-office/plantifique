from pydantic import BaseModel
from typing import Optional


class ProductSchema(BaseModel):
    id: str
    title: str
    status: str
    category_id: Optional[str]
    brand_name: Optional[str]
    price: Optional[float]
