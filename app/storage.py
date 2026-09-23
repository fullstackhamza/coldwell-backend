"""Storage for uploaded product images — Cloudinary in production, local
disk in development.

Which backend is used is decided automatically, once, at import time:
if CLOUDINARY_CLOUD_NAME/API_KEY/API_SECRET are all set (see app/config.py),
every upload goes to Cloudinary. Otherwise everything falls back to local
disk, so `uvicorn app.main:app --reload` on your own machine still works
with zero extra setup.

Everything outside this file — routers, models, the frontend — only ever
sees the URL that save_upload() returns, so which backend is active is
invisible to the rest of the app.
"""

import secrets
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from .config import settings

ALLOWED_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}

UPLOAD_ROOT = Path(settings.upload_dir)

USE_CLOUDINARY = bool(
    settings.cloudinary_cloud_name
    and settings.cloudinary_api_key
    and settings.cloudinary_api_secret
)

if USE_CLOUDINARY:
    import cloudinary
    import cloudinary.uploader

    cloudinary.config(
        cloud_name=settings.cloudinary_cloud_name,
        api_key=settings.cloudinary_api_key,
        api_secret=settings.cloudinary_api_secret,
        secure=True,
    )


def _validate(file: UploadFile) -> str:
    ext = ALLOWED_CONTENT_TYPES.get(file.content_type or "")
    if not ext:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only JPEG, PNG, WEBP, or GIF images are allowed",
        )
    return ext


def _save_local(file: UploadFile, ext: str) -> str:
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{ext}"
    dest = UPLOAD_ROOT / filename

    max_bytes = settings.max_upload_mb * 1024 * 1024
    written = 0
    with open(dest, "wb") as out:
        while chunk := file.file.read(1024 * 1024):
            written += len(chunk)
            if written > max_bytes:
                out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"Image must be under {settings.max_upload_mb}MB",
                )
            out.write(chunk)

    if written == 0:
        dest.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file"
        )

    base = settings.public_base_url.rstrip("/")
    return f"{base}/uploads/{filename}"


def _save_cloudinary(file: UploadFile) -> str:
    # Cloudinary enforces its own size/type rules and streams the upload
    # itself, so we just do a lightweight size pre-check to fail fast with
    # a clear error instead of waiting on a slow reject from their API.
    file.file.seek(0, 2)  # seek to end
    size = file.file.tell()
    file.file.seek(0)
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if size > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Image must be under {settings.max_upload_mb}MB",
        )
    if size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file"
        )

    try:
        result = cloudinary.uploader.upload(
            file.file,
            folder="coldwell",
            resource_type="image",
        )
    except Exception as exc:  # cloudinary raises its own generic Error type
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Image upload to Cloudinary failed: {exc}",
        ) from exc

    return result["secure_url"]


def save_upload(file: UploadFile) -> str:
    """Validates and saves an uploaded image, returning its public URL.
    Routes to Cloudinary or local disk automatically — see module docstring."""
    ext = _validate(file)
    if USE_CLOUDINARY:
        return _save_cloudinary(file)
    return _save_local(file, ext)


def delete_upload(url: str) -> None:
    """Best-effort delete when an image is removed from a product. Silently
    ignores URLs that aren't ours or files that are already gone."""
    if USE_CLOUDINARY:
        if "res.cloudinary.com" not in url:
            return
        # Cloudinary URLs look like:
        # https://res.cloudinary.com/<cloud>/image/upload/v123/coldwell/<id>.jpg
        # The public_id (what delete needs) is "coldwell/<id>" — everything
        # after the /v<digits>/ segment, minus the file extension.
        try:
            after_version = url.split("/upload/", 1)[1]
            path_part = after_version.split("/", 1)[1]  # drop the v<digits> segment
            public_id = path_part.rsplit(".", 1)[0]
        except IndexError:
            return
        try:
            cloudinary.uploader.destroy(public_id, resource_type="image")
        except Exception:
            # Best-effort — a failed cleanup shouldn't block the product
            # update/delete that triggered it.
            pass
        return

    marker = "/uploads/"
    if marker not in url:
        return
    filename = url.split(marker, 1)[1]
    if "/" in filename or ".." in filename:
        return
    (UPLOAD_ROOT / filename).unlink(missing_ok=True)


def new_upload_token() -> str:
    """Unused today, reserved for signing direct-to-storage uploads if this
    moves to presigned URLs later."""
    return secrets.token_urlsafe(16)
