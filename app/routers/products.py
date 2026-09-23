import secrets
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pymongo import ReturnDocument
from pymongo.database import Database

from ..auth_utils import get_current_admin_id
from ..database import get_db
from ..models.product import Product, ProductCreate, ProductUpdate

router = APIRouter(prefix="/api/products", tags=["products"])


def _doc_to_product(doc: dict) -> dict:
    doc = dict(doc)
    doc.pop("_id", None)
    return doc


@router.get("", response_model=list[Product])
def list_products(
    response: Response,
    category: Optional[str] = None,
    subcategory: Optional[list[str]] = Query(default=None),
    colors: Optional[list[str]] = Query(default=None),
    sizes: Optional[list[str]] = Query(default=None),
    price_min: Optional[float] = None,
    price_max: Optional[float] = None,
    collection: Optional[list[str]] = Query(default=None),
    on_sale: Optional[bool] = None,
    in_stock: Optional[bool] = None,
    sort: str = "recommended",
    q: Optional[str] = Query(default=None, description="Free-text search over name/description"),
    page: Optional[int] = Query(default=None, ge=1),
    limit: Optional[int] = Query(default=None, ge=1, le=100),
    db: Database = Depends(get_db),
):
    query: dict = {}
    if category:
        query["category"] = category
    if q:
        # Case-insensitive substring match on name/description/subcategory.
        # Fine for a demo-sized catalog; move to a text index ($text) or a
        # real search service (Meilisearch/Algolia) once the catalog is
        # large enough that this table scan gets slow.
        query["$or"] = [
            {"name": {"$regex": q, "$options": "i"}},
            {"description": {"$regex": q, "$options": "i"}},
            {"subcategory": {"$regex": q, "$options": "i"}},
        ]
    if subcategory:
        query["subcategory"] = {"$in": subcategory}
    if colors:
        query["colors.name"] = {"$in": colors}
    if sizes:
        query["sizes"] = {"$in": sizes}
    if price_min is not None or price_max is not None:
        price_query: dict = {}
        if price_min is not None:
            price_query["$gte"] = price_min
        if price_max is not None:
            price_query["$lte"] = price_max
        query["price"] = price_query
    if collection:
        conditions = []
        if "new-arrivals" in collection:
            conditions.append({"is_new_arrival": True})
        if "best-sellers" in collection:
            conditions.append({"is_best_seller": True})
        if conditions:
            # Combine with the search $or (if present) via $and, rather than
            # overwriting it — both conditions must hold.
            if "$or" in query:
                query["$and"] = [{"$or": query.pop("$or")}, {"$or": conditions}]
            else:
                query["$or"] = conditions
    if on_sale:
        query["compare_at_price"] = {"$ne": None}

    cursor = db.products.find(query)

    sort_map = {
        "newest": [("created_at", -1)],
        "price-asc": [("price", 1)],
        "price-desc": [("price", -1)],
        "best-selling": [("popularity", -1)],
    }
    if sort in sort_map:
        cursor = cursor.sort(sort_map[sort])

    docs = [_doc_to_product(doc) for doc in cursor]

    if in_stock:
        docs = [
            d
            for d in docs
            if any(
                s not in (d.get("unavailable_sizes") or [])
                for s in d.get("sizes") or []
            )
        ]

    # Pagination is opt-in and applied last (after the in_stock filter,
    # which can't be expressed in the Mongo query itself) so existing
    # callers that don't pass page/limit keep getting the full list —
    # nothing about the current frontend behavior changes unless it starts
    # sending these params.
    response.headers["X-Total-Count"] = str(len(docs))
    if page is not None or limit is not None:
        page = page or 1
        limit = limit or 24
        start = (page - 1) * limit
        docs = docs[start : start + limit]

    return docs


@router.get("/{slug}", response_model=Product)
def get_product(slug: str, db: Database = Depends(get_db)):
    doc = db.products.find_one({"slug": slug})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        )
    return _doc_to_product(doc)


@router.post("", response_model=Product, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProductCreate,
    db: Database = Depends(get_db),
    # Requires a real admin account (see app/create_admin.py) — a plain
    # logged-in customer gets a 403 here.
    _admin_id: str = Depends(get_current_admin_id),
):
    if db.products.find_one({"slug": payload.slug}):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A product with this slug already exists",
        )
    doc = payload.model_dump()
    doc["id"] = secrets.token_hex(4)
    doc["created_at"] = datetime.now(timezone.utc).date().isoformat()
    db.products.insert_one(doc)
    return _doc_to_product(doc)


@router.put("/{slug}", response_model=Product)
def update_product(
    slug: str,
    payload: ProductUpdate,
    db: Database = Depends(get_db),
    _admin_id: str = Depends(get_current_admin_id),
):
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        doc = db.products.find_one({"slug": slug})
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
            )
        return _doc_to_product(doc)

    result = db.products.find_one_and_update(
        {"slug": slug},
        {"$set": updates},
        return_document=ReturnDocument.AFTER,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        )
    return _doc_to_product(result)


@router.delete("/{slug}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    slug: str,
    db: Database = Depends(get_db),
    _admin_id: str = Depends(get_current_admin_id),
):
    result = db.products.delete_one({"slug": slug})
    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        )
