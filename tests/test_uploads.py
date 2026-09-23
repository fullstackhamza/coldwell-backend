import io

from tests.test_products import _signup, _signup_admin


def test_upload_requires_admin(api_client):
    response = api_client.post(
        "/api/uploads",
        files={"file": ("photo.jpg", io.BytesIO(b"fake-bytes"), "image/jpeg")},
    )
    assert response.status_code == 401

    headers = {"Authorization": f"Bearer {_signup(api_client)}"}
    response = api_client.post(
        "/api/uploads",
        files={"file": ("photo.jpg", io.BytesIO(b"fake-bytes"), "image/jpeg")},
        headers=headers,
    )
    assert response.status_code == 403


def test_upload_accepts_image_and_returns_url(api_client, db, tmp_path, monkeypatch):
    import app.storage as storage

    monkeypatch.setattr(storage, "UPLOAD_ROOT", tmp_path)

    headers = {"Authorization": f"Bearer {_signup_admin(api_client, db)}"}
    response = api_client.post(
        "/api/uploads",
        files={"file": ("photo.jpg", io.BytesIO(b"fake-jpeg-bytes"), "image/jpeg")},
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["url"].endswith(".jpg")
    assert (tmp_path / body["url"].rsplit("/", 1)[-1]).exists()


def test_upload_rejects_non_image(api_client, db):
    headers = {"Authorization": f"Bearer {_signup_admin(api_client, db)}"}
    response = api_client.post(
        "/api/uploads",
        files={"file": ("notes.txt", io.BytesIO(b"hello"), "text/plain")},
        headers=headers,
    )
    assert response.status_code == 415
