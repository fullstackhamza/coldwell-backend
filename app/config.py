from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "coldwell"
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60 * 24 * 7  # 7 days
    cors_origins: str = "http://localhost:3000"

    # Local file storage for product images (used only when the Cloudinary
    # settings below are NOT set — i.e. local development by default).
    upload_dir: str = "uploads"
    max_upload_mb: int = 5
    # Base URL this API is reachable at, used to build absolute image URLs
    # returned to the frontend (e.g. http://localhost:8000 in dev, your real
    # API domain in production). Unused once Cloudinary is configured.
    public_base_url: str = "http://localhost:8000"

    # Cloudinary — set these three in production (free tier, persists
    # across redeploys, unlike local disk on Render/Railway/etc). Get them
    # from your Cloudinary dashboard after signing up free. When all three
    # are set, app/storage.py automatically uses Cloudinary instead of
    # local disk — no other code changes needed.
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""

    # Simple in-memory rate limit for auth endpoints (per IP).
    auth_rate_limit_per_minute: int = 10


settings = Settings()
