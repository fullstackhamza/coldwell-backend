import mongomock
import pytest
from fastapi.testclient import TestClient

from app.database import ensure_indexes, get_db
from app.main import app


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """The rate limiter keeps in-memory state keyed by IP, and every
    TestClient instance shares the same fake IP ("testclient") — without
    this, hits would accumulate across unrelated tests in the same run and
    cause unrelated tests to fail with 429s that have nothing to do with
    what they're testing."""
    from app import rate_limit

    rate_limit._hits.clear()
    yield
    rate_limit._hits.clear()


@pytest.fixture()
def db():
    client = mongomock.MongoClient()
    test_db = client["test_db"]
    ensure_indexes(test_db)
    return test_db


@pytest.fixture()
def api_client(db):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
