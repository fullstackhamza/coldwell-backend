"""Minimal in-memory rate limiter for auth endpoints.

Good enough for a single-process deployment (one uvicorn worker). If you
scale to multiple workers/instances, replace the in-memory dict with Redis
(e.g. `redis.incr` + `EXPIRE`) so the count is shared — each process
currently tracks its own counts independently.
"""

import time
from collections import defaultdict

from fastapi import HTTPException, Request, status

from .config import settings

# ip -> list of request timestamps within the current window
_hits: dict[str, list[float]] = defaultdict(list)

WINDOW_SECONDS = 60


def rate_limit_auth(request: Request) -> None:
    """FastAPI dependency — add to login/signup to throttle brute-force
    attempts. Keyed by client IP."""
    ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    window_start = now - WINDOW_SECONDS

    hits = _hits[ip]
    # Drop timestamps outside the current window.
    while hits and hits[0] < window_start:
        hits.pop(0)

    if len(hits) >= settings.auth_rate_limit_per_minute:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts — please wait a minute and try again",
        )

    hits.append(now)
