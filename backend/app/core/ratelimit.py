"""A deliberately tiny in-process rate limiter.

Single-process, in-memory — adequate for the 24-hour MVP demo (PRD NFR-P4 asks
for rate limiting on login and request creation). Not shared across workers.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from app.core.errors import rate_limited

_hits: dict[str, deque[float]] = defaultdict(deque)


def check_rate_limit(key: str, limit: int, window_seconds: int) -> None:
    """Record a hit for `key`; raise 429 if it exceeds `limit` in the window."""
    now = time.monotonic()
    bucket = _hits[key]
    while bucket and now - bucket[0] > window_seconds:
        bucket.popleft()
    if len(bucket) >= limit:
        raise rate_limited()
    bucket.append(now)


def reset() -> None:
    """Clear all buckets (used by tests)."""
    _hits.clear()
