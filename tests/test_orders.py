ADDRESS = {
    "fullName": "Ali Khan",
    "phone": "03001234567",
    "email": "ali@example.com",
    "street": "123 Main St",
    "city": "Lahore",
    "province": "Punjab",
    "postalCode": "54000",
}


def _signup(api_client, email="orders@example.com"):
    resp = api_client.post(
        "/api/auth/signup",
        json={"fullName": "Order Tester", "email": email, "password": "testpass1"},
    )
    assert resp.status_code == 201
    return resp.json()["accessToken"]


def _signup_admin(api_client, db, email="admin@example.com"):
    token = _signup(api_client, email=email)
    db.users.update_one({"email": email}, {"$set": {"role": "admin"}})
    return token


def _create_product(api_client, headers, slug="test-shirt", price=1000):
    resp = api_client.post(
        "/api/products",
        json={
            "slug": slug,
            "name": "Test Shirt",
            "category": "Men",
            "subcategory": "T-Shirts",
            "price": price,
            "colors": [{"name": "Black", "hex": "#000"}],
            "sizes": ["M", "L"],
            "description": "d",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()


def test_guest_order_creation_and_lookup(api_client, db):
    headers = {"Authorization": f"Bearer {_signup_admin(api_client, db)}"}
    _create_product(api_client, headers, price=1000)

    order_payload = {
        "items": [
            {"productSlug": "test-shirt", "size": "M", "color": "Black", "quantity": 2}
        ],
        "address": ADDRESS,
        "paymentMethod": "cod",
    }
    # No Authorization header — this is a guest checkout.
    create_resp = api_client.post("/api/orders", json=order_payload)
    assert create_resp.status_code == 201
    order = create_resp.json()
    assert order["subtotal"] == 2000
    assert order["shipping"] == 200  # under the free-delivery threshold
    assert order["total"] == 2200
    assert order["userId"] is None
    assert order["status"] == "Pending"

    lookup_resp = api_client.get(f"/api/orders/{order['orderNumber']}")
    assert lookup_resp.status_code == 200
    assert lookup_resp.json()["orderNumber"] == order["orderNumber"]


def test_order_price_always_comes_from_database(api_client, db):
    headers = {"Authorization": f"Bearer {_signup_admin(api_client, db)}"}
    _create_product(api_client, headers, price=1000)

    order_payload = {
        # A cart item schema doesn't even accept a client-supplied price,
        # but this confirms the server-side price (1000) wins regardless.
        "items": [
            {"productSlug": "test-shirt", "size": "M", "color": "Black", "quantity": 1}
        ],
        "address": ADDRESS,
        "paymentMethod": "cod",
    }
    resp = api_client.post("/api/orders", json=order_payload)
    assert resp.status_code == 201
    assert resp.json()["subtotal"] == 1000


def test_free_shipping_over_threshold(api_client, db):
    headers = {"Authorization": f"Bearer {_signup_admin(api_client, db)}"}
    _create_product(api_client, headers, slug="expensive-item", price=6000)

    order_payload = {
        "items": [
            {
                "productSlug": "expensive-item",
                "size": "M",
                "color": "Black",
                "quantity": 1,
            }
        ],
        "address": ADDRESS,
        "paymentMethod": "cod",
    }
    resp = api_client.post("/api/orders", json=order_payload)
    assert resp.status_code == 201
    assert resp.json()["shipping"] == 0


def test_order_with_unknown_product_rejected(api_client):
    order_payload = {
        "items": [
            {
                "productSlug": "does-not-exist",
                "size": "M",
                "color": "Black",
                "quantity": 1,
            }
        ],
        "address": ADDRESS,
        "paymentMethod": "cod",
    }
    resp = api_client.post("/api/orders", json=order_payload)
    assert resp.status_code == 400


def test_order_with_no_items_rejected(api_client):
    resp = api_client.post(
        "/api/orders", json={"items": [], "address": ADDRESS, "paymentMethod": "cod"}
    )
    assert resp.status_code == 400


def test_my_orders_requires_auth_and_returns_only_own_orders(api_client, db):
    headers = {
        "Authorization": f"Bearer {_signup_admin(api_client, db, email='mine@example.com')}"
    }
    _create_product(api_client, headers, slug="mine-item", price=500)

    order_payload = {
        "items": [
            {"productSlug": "mine-item", "size": "M", "color": "Black", "quantity": 1}
        ],
        "address": ADDRESS,
        "paymentMethod": "cod",
    }
    api_client.post("/api/orders", json=order_payload, headers=headers)

    no_auth = api_client.get("/api/orders/mine")
    assert no_auth.status_code == 401

    mine_resp = api_client.get("/api/orders/mine", headers=headers)
    assert mine_resp.status_code == 200
    assert len(mine_resp.json()) == 1


def test_order_lookup_without_phone_still_works(api_client, db):
    """The order-confirmation page relies on this working with no phone."""
    headers = {
        "Authorization": f"Bearer {_signup_admin(api_client, db, email='lookup@example.com')}"
    }
    _create_product(api_client, headers, slug="lookup-item", price=500)
    order = api_client.post(
        "/api/orders",
        json={
            "items": [
                {"productSlug": "lookup-item", "size": "M", "color": "Black", "quantity": 1}
            ],
            "address": ADDRESS,
            "paymentMethod": "cod",
        },
    ).json()

    resp = api_client.get(f"/api/orders/{order['orderNumber']}")
    assert resp.status_code == 200


def test_order_lookup_with_correct_phone_succeeds(api_client, db):
    headers = {
        "Authorization": f"Bearer {_signup_admin(api_client, db, email='phone1@example.com')}"
    }
    _create_product(api_client, headers, slug="phone-item", price=500)
    order = api_client.post(
        "/api/orders",
        json={
            "items": [
                {"productSlug": "phone-item", "size": "M", "color": "Black", "quantity": 1}
            ],
            "address": ADDRESS,
            "paymentMethod": "cod",
        },
    ).json()

    resp = api_client.get(
        f"/api/orders/{order['orderNumber']}",
        params={"phone": ADDRESS["phone"]},
    )
    assert resp.status_code == 200


def test_order_lookup_with_wrong_phone_returns_not_found(api_client, db):
    headers = {
        "Authorization": f"Bearer {_signup_admin(api_client, db, email='phone2@example.com')}"
    }
    _create_product(api_client, headers, slug="phone-item-2", price=500)
    order = api_client.post(
        "/api/orders",
        json={
            "items": [
                {"productSlug": "phone-item-2", "size": "M", "color": "Black", "quantity": 1}
            ],
            "address": ADDRESS,
            "paymentMethod": "cod",
        },
    ).json()

    resp = api_client.get(
        f"/api/orders/{order['orderNumber']}",
        params={"phone": "03009999999"},
    )
    assert resp.status_code == 404


def test_list_all_orders_requires_admin(api_client, db):
    customer_headers = {
        "Authorization": f"Bearer {_signup(api_client, email='plain@example.com')}"
    }
    no_auth = api_client.get("/api/orders")
    assert no_auth.status_code == 401

    as_customer = api_client.get("/api/orders", headers=customer_headers)
    assert as_customer.status_code == 403


def test_admin_can_list_all_orders_across_users(api_client, db):
    admin_headers = {
        "Authorization": f"Bearer {_signup_admin(api_client, db, email='listadmin@example.com')}"
    }
    _create_product(api_client, admin_headers, slug="list-item", price=500)

    # One guest order, one order placed by a different logged-in customer.
    api_client.post(
        "/api/orders",
        json={
            "items": [{"productSlug": "list-item", "size": "M", "color": "Black", "quantity": 1}],
            "address": ADDRESS,
            "paymentMethod": "cod",
        },
    )
    other_customer_headers = {
        "Authorization": f"Bearer {_signup(api_client, email='othercustomer@example.com')}"
    }
    api_client.post(
        "/api/orders",
        json={
            "items": [{"productSlug": "list-item", "size": "M", "color": "Black", "quantity": 1}],
            "address": ADDRESS,
            "paymentMethod": "cod",
        },
        headers=other_customer_headers,
    )

    resp = api_client.get("/api/orders", headers=admin_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_update_order_status_requires_admin(api_client, db):
    admin_headers = {
        "Authorization": f"Bearer {_signup_admin(api_client, db, email='statusadmin@example.com')}"
    }
    _create_product(api_client, admin_headers, slug="status-item", price=500)
    order = api_client.post(
        "/api/orders",
        json={
            "items": [{"productSlug": "status-item", "size": "M", "color": "Black", "quantity": 1}],
            "address": ADDRESS,
            "paymentMethod": "cod",
        },
    ).json()

    customer_headers = {
        "Authorization": f"Bearer {_signup(api_client, email='statuscustomer@example.com')}"
    }
    as_customer = api_client.patch(
        f"/api/orders/{order['orderNumber']}/status",
        json={"status": "Confirmed"},
        headers=customer_headers,
    )
    assert as_customer.status_code == 403


def test_admin_can_update_order_status(api_client, db):
    admin_headers = {
        "Authorization": f"Bearer {_signup_admin(api_client, db, email='statusadmin2@example.com')}"
    }
    _create_product(api_client, admin_headers, slug="status-item-2", price=500)
    order = api_client.post(
        "/api/orders",
        json={
            "items": [{"productSlug": "status-item-2", "size": "M", "color": "Black", "quantity": 1}],
            "address": ADDRESS,
            "paymentMethod": "cod",
        },
    ).json()

    resp = api_client.patch(
        f"/api/orders/{order['orderNumber']}/status",
        json={"status": "Shipped"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "Shipped"

    # Confirm it actually persisted.
    check = api_client.get(f"/api/orders/{order['orderNumber']}")
    assert check.json()["status"] == "Shipped"


def test_update_order_status_rejects_invalid_status(api_client, db):
    admin_headers = {
        "Authorization": f"Bearer {_signup_admin(api_client, db, email='statusadmin3@example.com')}"
    }
    _create_product(api_client, admin_headers, slug="status-item-3", price=500)
    order = api_client.post(
        "/api/orders",
        json={
            "items": [{"productSlug": "status-item-3", "size": "M", "color": "Black", "quantity": 1}],
            "address": ADDRESS,
            "paymentMethod": "cod",
        },
    ).json()

    resp = api_client.patch(
        f"/api/orders/{order['orderNumber']}/status",
        json={"status": "NotARealStatus"},
        headers=admin_headers,
    )
    assert resp.status_code == 400


def test_update_status_for_unknown_order_returns_404(api_client, db):
    admin_headers = {
        "Authorization": f"Bearer {_signup_admin(api_client, db, email='statusadmin4@example.com')}"
    }
    resp = api_client.patch(
        "/api/orders/DOESNOTEXIST/status",
        json={"status": "Confirmed"},
        headers=admin_headers,
    )
    assert resp.status_code == 404
