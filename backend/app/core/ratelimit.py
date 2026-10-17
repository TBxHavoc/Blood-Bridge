"""A deliberately tiny in-process rate limiter.

Single-process, in-memory — adequate for the 24-hour MVP demo (PRD NFR-P4 asks
for rate limiting on login and request creation). Not shared across workers.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from app.core.errors import rate_limited

_hits: dict[str, deque[float]] = defaultdict(deque)

# Keys idle for longer than the largest expected window can be dropped; prune
# at most once per interval so the map cannot grow without bound.
_MAX_WINDOW_SECONDS = 3600.0
_PRUNE_INTERVAL_SECONDS = 300.0
_last_prune = 0.0


def _prune(now: float) -> None:
    for key in list(_hits.keys()):
        bucket = _hits[key]
        if not bucket or now - bucket[-1] > _MAX_WINDOW_SECONDS:
            del _hits[key]


def check_rate_limit(key: str, limit: int, window_seconds: int) -> None:
    """Record a hit for `key`; raise 429 if it exceeds `limit` in the window."""
    global _last_prune
    now = time.monotonic()
    if now - _last_prune > _PRUNE_INTERVAL_SECONDS:
        _prune(now)
        _last_prune = now
    bucket = _hits[key]
    while bucket and now - bucket[0] > window_seconds:
        bucket.popleft()
    if len(bucket) >= limit:
        raise rate_limited()
    bucket.append(now)


def reset() -> None:
    """Clear all buckets (used by tests)."""
    global _last_prune
    _hits.clear()
    _last_prune = 0.0
