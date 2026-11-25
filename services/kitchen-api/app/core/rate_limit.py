import asyncio
import heapq
import math
from collections import deque
from dataclasses import dataclass
from time import monotonic


@dataclass
class _Bucket:
    timestamps: deque[float]
    window_seconds: float


class InMemoryRateLimiter:
    def __init__(
        self,
        max_buckets: int = 10_000,
        cleanup_interval_seconds: float = 60,
    ) -> None:
        if max_buckets <= 0 or cleanup_interval_seconds <= 0:
            raise ValueError(
                "Rate limiter capacity and cleanup interval must be positive"
            )
        self._buckets: dict[tuple[str, str], _Bucket] = {}
        self._expirations: list[tuple[float, tuple[str, str]]] = []
        self._lock = asyncio.Lock()
        self._max_buckets = max_buckets
        self._cleanup_interval_seconds = cleanup_interval_seconds
        self._last_cleanup = monotonic()

    async def check(
        self,
        scope: str,
        client_ip: str,
        limit: int,
        window_seconds: float,
    ) -> int | None:
        if limit <= 0 or window_seconds <= 0:
            raise ValueError("Rate limit and window must be positive")
        now = monotonic()
        async with self._lock:
            if now - self._last_cleanup >= self._cleanup_interval_seconds:
                self._prune(now)
            key = (scope, client_ip)
            bucket = self._buckets.get(key)
            if bucket is None:
                if len(self._buckets) >= self._max_buckets:
                    if self._next_expiration() <= now:
                        self._prune(now)
                if len(self._buckets) >= self._max_buckets:
                    return max(1, math.ceil(self._next_expiration() - now))
                bucket = _Bucket(deque(), window_seconds)
                self._buckets[key] = bucket
            cutoff = now - window_seconds
            while bucket.timestamps and bucket.timestamps[0] <= cutoff:
                bucket.timestamps.popleft()
            window_changed = bucket.window_seconds != window_seconds
            bucket.window_seconds = window_seconds
            if len(bucket.timestamps) >= limit:
                if window_changed:
                    self._record_expiration(key, bucket)
                return max(
                    1,
                    math.ceil(window_seconds - (now - bucket.timestamps[0])),
                )
            bucket.timestamps.append(now)
            self._record_expiration(key, bucket)
            return None

    def _record_expiration(
        self, key: tuple[str, str], bucket: _Bucket
    ) -> None:
        heapq.heappush(
            self._expirations,
            (bucket.timestamps[-1] + bucket.window_seconds, key),
        )
        if len(self._expirations) > 2 * self._max_buckets:
            self._rebuild_expirations()

    def _next_expiration(self) -> float:
        while self._expirations:
            expiry, key = self._expirations[0]
            bucket = self._buckets.get(key)
            if (
                bucket is not None
                and bucket.timestamps
                and expiry == bucket.timestamps[-1] + bucket.window_seconds
            ):
                return expiry
            heapq.heappop(self._expirations)
        return math.inf

    def _rebuild_expirations(self) -> None:
        self._expirations = [
            (bucket.timestamps[-1] + bucket.window_seconds, key)
            for key, bucket in self._buckets.items()
            if bucket.timestamps
        ]
        heapq.heapify(self._expirations)

    def _prune(self, now: float) -> None:
        stale = [
            key
            for key, bucket in self._buckets.items()
            if not bucket.timestamps
            or bucket.timestamps[-1] <= now - bucket.window_seconds
        ]
        for key in stale:
            del self._buckets[key]
        self._rebuild_expirations()
        self._last_cleanup = now
