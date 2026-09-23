from typing import Optional

from pydantic import Field

from .common import CamelModel


class ProductColor(CamelModel):
    name: str
    hex: str


class ProductBase(CamelModel):
    name: str
    category: str  # "Men" | "Women"
    subcategory: str
    price: float
    compare_at_price: Optional[float] = None
    colors: list[ProductColor] = Field(default_factory=list)
    sizes: list[str] = Field(default_factory=list)
    unavailable_sizes: list[str] = Field(default_factory=list)
    # Absolute URLs — either local /uploads/... (see app/storage.py) or a
    # remote URL (Unsplash/Cloudinary) for seeded demo products. First image
    # is the card/thumbnail image; the rest form the product page gallery.
    images: list[str] = Field(default_factory=list)
    description: str
    is_new_arrival: bool = False
    is_best_seller: bool = False
    popularity: int = 0
    rating: float = 0
    review_count: int = 0


class ProductCreate(ProductBase):
    slug: str


class ProductUpdate(CamelModel):
    name: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    price: Optional[float] = None
    compare_at_price: Optional[float] = None
    colors: Optional[list[ProductColor]] = None
    sizes: Optional[list[str]] = None
    unavailable_sizes: Optional[list[str]] = None
    images: Optional[list[str]] = None
    description: Optional[str] = None
    is_new_arrival: Optional[bool] = None
    is_best_seller: Optional[bool] = None
    popularity: Optional[int] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None


class Product(ProductBase):
    id: str
    slug: str
    created_at: str
