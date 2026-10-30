"""The cleaned catalogue as the rest of the service sees it."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

Availability = Literal["in_stock", "low_stock", "out_of_stock", "unlimited"]


class Product(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    product_id: str
    name: str
    category: str
    category_slug: str
    subcategory: str
    brand: str
    price_eur: float
    stock: int
    availability: Availability
    rating: float | None
    reviews_count: int | None
    recipient: str
    occasions: list[str]
    tags: list[str]
    color: str | None
    material: str | None
    gift_wrap: bool
    shipping_days: int
    is_digital: bool
    description: str
    also_listed_as: list[str]
    search_primary: bool
    search_text: str
    search_text_compact: str
