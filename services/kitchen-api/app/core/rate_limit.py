import asyncio
import math
from collections import deque
from dataclasses import dataclass
from time import monotonic


@dataclass
class _Bucket:
    timestamps: deque[float]
    window_seconds: float


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._buckets: dict[tuple[str, str], _Bucket] = {}
        self._lock = asyncio.Lock()

    async def check(
        self,
        scope: str,
        client_ip: str,
        limit: int,
        window_seconds: float,
    ) -> int | None:
        now = monotonic()
        async with self._lock:
            self._prune(now)
            key = (scope, client_ip)
            bucket = self._buckets.setdefault(
                key,
                _Bucket(deque(), window_seconds),
            )
            cutoff = now - window_seconds
            while bucket.timestamps and bucket.timestamps[0] <= cutoff:
                bucket.timestamps.popleft()
            bucket.window_seconds = window_seconds
            if len(bucket.timestamps) >= limit:
                return max(
                    1,
                    math.ceil(window_seconds - (now - bucket.timestamps[0])),
                )
            bucket.timestamps.append(now)
            return None

    def _prune(self, now: float) -> None:
        stale = [
            key
            for key, bucket in self._buckets.items()
            if not bucket.timestamps
            or bucket.timestamps[-1] <= now - bucket.window_seconds
        ]
        for key in stale:
            del self._buckets[key]
