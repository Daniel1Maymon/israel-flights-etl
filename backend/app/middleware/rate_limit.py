"""
Per-client request rate limiting.

Why this is hand-rolled rather than slowapi: slowapi's global middleware discovers the
target route by walking `app.routes` and reading `.endpoint`. This FastAPI version wraps
`include_router()` into a single `_IncludedRouter` entry with no `.endpoint`, so route
lookup returns None, every request is treated as exempt, and the limiter silently counts
nothing. It presents as fully configured while enforcing nothing -- see
tests/test_security_dos.py::TestRateLimiting.

This implementation needs no route discovery: it keys off the client identity and the
request path only.

Algorithm: fixed window. Simple and cheap, with one known caveat -- a client can send up
to 2x the limit across a window boundary (limit at the end of one window, limit at the
start of the next). That is acceptable here: the goal is bounding sustained bulk
collection, not policing precise burst shape.
"""
from __future__ import annotations

import time
from typing import Callable, Iterable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = structlog.get_logger()

# Ceiling on tracked client keys. Without it, an attacker rotating source addresses
# would grow the counter dict without bound -- turning the defence into a memory leak.
MAX_TRACKED_KEYS = 100_000


def client_key_from_request(request: Request) -> str:
    """
    Identify the caller.

    X-Forwarded-For is client-controlled. Taking the leftmost entry would let an attacker
    send a random value per request and land in a fresh bucket every time -- a limiter
    that looks installed but counts nothing. The rightmost entry is the one appended by
    the trusted proxy immediately in front of this app.

    VERIFY before relying on this in production: log the raw header for one real request
    through Railway and confirm which position holds the true client IP. If Railway
    prepends rather than appends, change the index here.
    """
    xff = request.headers.get("x-forwarded-for")
    if xff:
        parts = [p.strip() for p in xff.split(",") if p.strip()]
        if parts:
            return parts[-1]
    return request.client.host if request.client else "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Fixed-window per-client limiter. Counters are per-process."""

    def __init__(
        self,
        app,
        limit: int,
        window_seconds: int = 60,
        exempt_paths: Iterable[str] = (),
        key_func: Callable[[Request], str] = client_key_from_request,
    ) -> None:
        super().__init__(app)
        self.limit = limit
        self.window_seconds = window_seconds
        self.exempt_paths = frozenset(exempt_paths)
        self.key_func = key_func
        # key -> [count, window_start_monotonic]
        self._hits: dict[str, list] = {}

    def _prune(self, now: float) -> None:
        """Drop expired buckets once the table grows past its ceiling."""
        if len(self._hits) <= MAX_TRACKED_KEYS:
            return
        cutoff = now - self.window_seconds
        stale = [k for k, (_, started) in self._hits.items() if started < cutoff]
        for k in stale:
            del self._hits[k]
        if len(self._hits) > MAX_TRACKED_KEYS:
            # Still oversized: the window is saturated with live keys. Reset rather than
            # grow without bound; a brief accounting gap beats exhausting memory.
            logger.warning("rate limit table saturated, resetting", tracked=len(self._hits))
            self._hits.clear()

    def _register_hit(self, key: str) -> tuple[bool, int, int]:
        """Return (allowed, remaining, retry_after_seconds)."""
        now = time.monotonic()
        self._prune(now)

        bucket = self._hits.get(key)
        if bucket is None or (now - bucket[1]) >= self.window_seconds:
            self._hits[key] = [1, now]
            return True, self.limit - 1, 0

        bucket[0] += 1
        if bucket[0] > self.limit:
            retry_after = max(1, int(self.window_seconds - (now - bucket[1])) + 1)
            return False, 0, retry_after
        return True, self.limit - bucket[0], 0

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.url.path in self.exempt_paths:
            return await call_next(request)

        key = self.key_func(request)
        allowed, remaining, retry_after = self._register_hit(key)

        if not allowed:
            logger.warning(
                "rate limit exceeded", path=request.url.path, retry_after=retry_after
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": "Too many requests. Please slow down.",
                    }
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(self.limit),
                    "X-RateLimit-Remaining": "0",
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
