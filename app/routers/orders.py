import random
import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pymongo import ReturnDocument
from pymongo.database import Database

from ..auth_utils import get_current_admin_id, get_current_user_id, get_optional_user_id
from ..database import get_db
from ..models.order import Order, OrderCreate, OrderItemOut, OrderStatusUpdate

router = APIRouter(prefix="/api/orders", tags=["orders"])

VALID_STATUSES = ["Pending", "Confirmed", "Processing", "Shipped", "Delivered", "Cancelled"]

# Keep in sync with the frontend's lib/site-config.ts
FREE_DELIVERY_THRESHOLD = 5000.0
STANDARD_DELIVERY_FEE = 200.0

# Kept in sync manually with the frontend's SITE_NAME (lib/site-config.ts)
SITE_PREFIX_SOURCE = "COLDWELL"


def _generate_order_number() -> str:
    letters = re.sub(r"[^A-Za-z]", "", SITE_PREFIX_SOURCE)[:2].upper() or "OR"
    digits = random.randint(100000, 999999)
    return f"{letters}{digits}"


def _doc_to_order(doc: dict) -> dict:
    doc = dict(doc)
    doc.pop("_id", None)
    return doc


@router.post("", response_model=Order, status_code=status.HTTP_201_CREATED)
def create_order(
    payload: OrderCreate,
    db: Database = Depends(get_db),
    user_id: Optional[str] = Depends(get_optional_user_id),
):
    if not payload.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot place an order with no items",
        )

    resolved_items: list[dict] = []
    subtotal = 0.0
    for cart_item in payload.items:
        product = db.products.find_one({"slug": cart_item.product_slug})
        if not product:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown product: {cart_item.product_slug}",
            )
        # Price always comes from the database — never trust a price the
        # client sends.
        subtotal += product["price"] * cart_item.quantity
        resolved_items.append(
            OrderItemOut(
                product_slug=cart_item.product_slug,
                name=product["name"],
                size=cart_item.size,
                color=cart_item.color,
                quantity=cart_item.quantity,
                price=product["price"],
            ).model_dump()
        )

    shipping = (
        0.0
        if subtotal == 0 or subtotal >= FREE_DELIVERY_THRESHOLD
        else STANDARD_DELIVERY_FEE
    )
    total = subtotal + shipping

    order_number = _generate_order_number()
    while db.orders.find_one({"order_number": order_number}):
        order_number = _generate_order_number()

    doc = {
        "order_number": order_number,
        "items": resolved_items,
        "address": payload.address.model_dump(),
        "payment_method": payload.payment_method,
        "subtotal": subtotal,
        "shipping": shipping,
        "total": total,
        "status": "Pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id,
    }
    db.orders.insert_one(doc)
    return _doc_to_order(doc)


@router.get("/mine", response_model=list[Order])
def list_my_orders(
    user_id: str = Depends(get_current_user_id), db: Database = Depends(get_db)
):
    docs = db.orders.find({"user_id": user_id}).sort("created_at", -1)
    return [_doc_to_order(d) for d in docs]


@router.get("", response_model=list[Order])
def list_all_orders(
    _admin_id: str = Depends(get_current_admin_id),
    db: Database = Depends(get_db),
):
    """Admin-only: every order in the store, newest first."""
    docs = db.orders.find({}).sort("created_at", -1)
    return [_doc_to_order(d) for d in docs]


@router.patch("/{order_number}/status", response_model=Order)
def update_order_status(
    order_number: str,
    payload: OrderStatusUpdate,
    _admin_id: str = Depends(get_current_admin_id),
    db: Database = Depends(get_db),
):
    """Admin-only: move an order through Pending → Confirmed → Processing →
    Shipped → Delivered (or Cancelled)."""
    if payload.status not in VALID_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Status must be one of: {', '.join(VALID_STATUSES)}",
        )
    result = db.orders.find_one_and_update(
        {"order_number": order_number},
        {"$set": {"status": payload.status}},
        return_document=ReturnDocument.AFTER,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Order not found"
        )
    return _doc_to_order(result)


@router.get("/{order_number}", response_model=Order)
def get_order(
    order_number: str,
    phone: Optional[str] = None,
    db: Database = Depends(get_db),
):
    doc = db.orders.find_one({"order_number": order_number})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Order not found"
        )
    # Phone is optional so the order-confirmation page (right after checkout)
    # can keep working with no extra input. When it IS provided — the guest
    # order-tracking flow — it must match, and a mismatch looks identical to
    # "not found" so this can't be used to enumerate orders by number alone.
    if phone is not None and doc["address"]["phone"] != phone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Order not found"
        )
    return _doc_to_order(doc)
