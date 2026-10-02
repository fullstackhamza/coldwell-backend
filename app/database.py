from functools import lru_cache

from pymongo import MongoClient
from pymongo.database import Database

from .config import settings


@lru_cache
def _get_client() -> MongoClient:
    return MongoClient(settings.mongodb_uri)


def get_db() -> Database:
    """FastAPI dependency — override this in tests with a mongomock database."""
    return _get_client()[settings.mongodb_db_name]


def ensure_indexes(db: Database) -> None:
    db.products.create_index("slug", unique=True)
    db.users.create_index("email", unique=True)
    db.orders.create_index("order_number", unique=True)
