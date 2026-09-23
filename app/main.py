from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import ensure_indexes, get_db
from .routers import auth, orders, products, uploads

app = FastAPI(title="Coldwell API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(products.router)
app.include_router(auth.router)
app.include_router(orders.router)
app.include_router(uploads.router)

# Serves whatever's saved by app/storage.py at /uploads/<filename>. If you
# move storage to S3/Cloudinary, this mount becomes unnecessary — the URLs
# save_upload() returns will point at that provider instead.
Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")


@app.on_event("startup")
def on_startup():
    # Makes sure the unique indexes (email, slug, order_number) exist even
    # on a brand-new database where nobody has run `python -m app.seed`
    # yet — previously these were only created by the seed script, so a
    # fresh production deploy could silently run without them.
    ensure_indexes(get_db())


@app.get("/api/health")
def health():
    return {"status": "ok"}

