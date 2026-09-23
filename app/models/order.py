from typing import Optional

from .common import CamelModel


class CartItemIn(CamelModel):
    product_slug: str
    size: str
    color: str
    quantity: int = 1


class ShippingAddress(CamelModel):
    full_name: str
    phone: str
    email: str
    street: str
    city: str
    province: str
    postal_code: str


class OrderCreate(CamelModel):
    items: list[CartItemIn]
    address: ShippingAddress
    payment_method: str  # "cod" | "online" | "bank-transfer"


class OrderStatusUpdate(CamelModel):
    status: str


class OrderItemOut(CamelModel):
    product_slug: str
    name: str
    size: str
    color: str
    quantity: int
    price: float


class Order(CamelModel):
    order_number: str
    items: list[OrderItemOut]
    address: ShippingAddress
    payment_method: str
    subtotal: float
    shipping: float
    total: float
    status: str = "Pending"
    created_at: str
    user_id: Optional[str] = None
