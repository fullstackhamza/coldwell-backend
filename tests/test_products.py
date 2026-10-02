def _signup(api_client, email="test@example.com"):
    response = api_client.post(
        "/api/auth/signup",
        json={"fullName": "Test User", "email": email, "password": "hunter2pass"},
    )
    assert response.status_code == 201
    return response.json()["accessToken"]


def _signup_admin(api_client, db, email="admin@example.com"):
    token = _signup(api_client, email=email)
    db.users.update_one({"email": email}, {"$set": {"role": "admin"}})
    return token


def test_list_products_empty(api_client):
    response = api_client.get("/api/products")
    assert response.status_code == 200
    assert response.json() == []


def test_create_requires_auth(api_client):
    response = api_client.post(
        "/api/products",
        json={
            "slug": "test-item",
            "name": "Test Item",
            "category": "Men",
            "subcategory": "T-Shirts",
            "price": 1000,
            "description": "A test product.",
        },
    )
    assert response.status_code == 401


def test_create_requires_admin_role(api_client, db):
    """A plain logged-in customer is not enough — must be an admin."""
    headers = {"Authorization": f"Bearer {_signup(api_client)}"}
    response = api_client.post(
        "/api/products",
        json={
            "slug": "test-item",
            "name": "Test Item",
            "category": "Men",
            "subcategory": "T-Shirts",
            "price": 1000,
            "description": "A test product.",
        },
        headers=headers,
    )
    assert response.status_code == 403


def test_create_list_get_update_delete_product(api_client, db):
    headers = {"Authorization": f"Bearer {_signup_admin(api_client, db)}"}

    create_resp = api_client.post(
        "/api/products",
        json={
            "slug": "test-item",
            "name": "Test Item",
            "category": "Men",
            "subcategory": "T-Shirts",
            "price": 1000,
            "colors": [{"name": "Black", "hex": "#000000"}],
            "sizes": ["S", "M", "L"],
            "description": "A test product.",
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    body = create_resp.json()
    assert body["slug"] == "test-item"
    assert body["compareAtPrice"] is None

    list_resp = api_client.get("/api/products")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    get_resp = api_client.get("/api/products/test-item")
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "Test Item"

    update_resp = api_client.put(
        "/api/products/test-item", json={"price": 1200}, headers=headers
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["price"] == 1200

    delete_resp = api_client.delete("/api/products/test-item", headers=headers)
    assert delete_resp.status_code == 204

    get_after_delete = api_client.get("/api/products/test-item")
    assert get_after_delete.status_code == 404


def test_duplicate_slug_rejected(api_client, db):
    headers = {"Authorization": f"Bearer {_signup_admin(api_client, db)}"}
    payload = {
        "slug": "dupe",
        "name": "Dupe",
        "category": "Men",
        "subcategory": "T-Shirts",
        "price": 1000,
        "description": "d",
    }
    first = api_client.post("/api/products", json=payload, headers=headers)
    assert first.status_code == 201
    second = api_client.post("/api/products", json=payload, headers=headers)
    assert second.status_code == 409


def test_filter_by_category_and_sale(api_client, db):
    headers = {"Authorization": f"Bearer {_signup_admin(api_client, db)}"}
    api_client.post(
        "/api/products",
        json={
            "slug": "a",
            "name": "A",
            "category": "Men",
            "subcategory": "T-Shirts",
            "price": 1000,
            "description": "d",
        },
        headers=headers,
    )
    api_client.post(
        "/api/products",
        json={
            "slug": "b",
            "name": "B",
            "category": "Women",
            "subcategory": "Dresses",
            "price": 3000,
            "compareAtPrice": 4000,
            "description": "d",
        },
        headers=headers,
    )

    men_only = api_client.get("/api/products", params={"category": "Men"})
    assert [p["slug"] for p in men_only.json()] == ["a"]

    on_sale = api_client.get("/api/products", params={"on_sale": True})
    assert [p["slug"] for p in on_sale.json()] == ["b"]


def test_sort_price_ascending(api_client, db):
    headers = {"Authorization": f"Bearer {_signup_admin(api_client, db)}"}
    for slug, price in [("cheap", 500), ("mid", 1500), ("expensive", 3000)]:
        api_client.post(
            "/api/products",
            json={
                "slug": slug,
                "name": slug,
                "category": "Men",
                "subcategory": "T-Shirts",
                "price": price,
                "description": "d",
            },
            headers=headers,
        )

    resp = api_client.get("/api/products", params={"sort": "price-asc"})
    assert [p["slug"] for p in resp.json()] == ["cheap", "mid", "expensive"]


def test_search_matches_name_and_description(api_client, db):
    headers = {"Authorization": f"Bearer {_signup_admin(api_client, db)}"}
    api_client.post(
        "/api/products",
        json={
            "slug": "linen-shirt",
            "name": "Linen Shirt",
            "category": "Men",
            "subcategory": "Shirts",
            "price": 2500,
            "description": "Breathable summer fabric.",
        },
        headers=headers,
    )
    api_client.post(
        "/api/products",
        json={
            "slug": "wool-coat",
            "name": "Wool Coat",
            "category": "Men",
            "subcategory": "Outerwear",
            "price": 8000,
            "description": "Warm for winter.",
        },
        headers=headers,
    )

    by_name = api_client.get("/api/products", params={"q": "linen"})
    assert [p["slug"] for p in by_name.json()] == ["linen-shirt"]

    by_description = api_client.get("/api/products", params={"q": "winter"})
    assert [p["slug"] for p in by_description.json()] == ["wool-coat"]

    no_match = api_client.get("/api/products", params={"q": "sneakers"})
    assert no_match.json() == []


def test_pagination_returns_total_count_header(api_client, db):
    headers = {"Authorization": f"Bearer {_signup_admin(api_client, db)}"}
    for i in range(5):
        api_client.post(
            "/api/products",
            json={
                "slug": f"item-{i}",
                "name": f"Item {i}",
                "category": "Men",
                "subcategory": "T-Shirts",
                "price": 1000,
                "description": "d",
            },
            headers=headers,
        )

    page_one = api_client.get("/api/products", params={"page": 1, "limit": 2})
    assert len(page_one.json()) == 2
    assert page_one.headers["X-Total-Count"] == "5"

    page_three = api_client.get("/api/products", params={"page": 3, "limit": 2})
    assert len(page_three.json()) == 1

    unpaginated = api_client.get("/api/products")
    assert len(unpaginated.json()) == 5
