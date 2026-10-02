def test_signup_and_get_me(api_client):
    signup_resp = api_client.post(
        "/api/auth/signup",
        json={
            "fullName": "Jane Doe",
            "email": "jane@example.com",
            "password": "supersecret1",
        },
    )
    assert signup_resp.status_code == 201
    body = signup_resp.json()
    assert body["user"]["email"] == "jane@example.com"
    token = body["accessToken"]

    me_resp = api_client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert me_resp.status_code == 200
    assert me_resp.json()["fullName"] == "Jane Doe"


def test_duplicate_signup_rejected(api_client):
    payload = {
        "fullName": "Jane",
        "email": "dupe@example.com",
        "password": "supersecret1",
    }
    first = api_client.post("/api/auth/signup", json=payload)
    assert first.status_code == 201
    second = api_client.post("/api/auth/signup", json=payload)
    assert second.status_code == 409


def test_login_success_and_failure(api_client):
    api_client.post(
        "/api/auth/signup",
        json={
            "fullName": "Jane",
            "email": "login@example.com",
            "password": "correcthorse",
        },
    )

    good = api_client.post(
        "/api/auth/login",
        json={"email": "login@example.com", "password": "correcthorse"},
    )
    assert good.status_code == 200
    assert "accessToken" in good.json()

    bad = api_client.post(
        "/api/auth/login",
        json={"email": "login@example.com", "password": "wrongpass"},
    )
    assert bad.status_code == 401


def test_me_requires_token(api_client):
    resp = api_client.get("/api/auth/me")
    assert resp.status_code == 401


def test_invalid_token_rejected(api_client):
    resp = api_client.get(
        "/api/auth/me", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert resp.status_code == 401


def test_login_rate_limited_after_too_many_attempts(api_client, monkeypatch):
    import app.rate_limit as rate_limit

    monkeypatch.setattr(rate_limit.settings, "auth_rate_limit_per_minute", 3)

    for _ in range(3):
        resp = api_client.post(
            "/api/auth/login",
            json={"email": "nobody@example.com", "password": "wrong"},
        )
        assert resp.status_code == 401  # wrong creds, but not yet rate limited

    blocked = api_client.post(
        "/api/auth/login",
        json={"email": "nobody@example.com", "password": "wrong"},
    )
    assert blocked.status_code == 429
