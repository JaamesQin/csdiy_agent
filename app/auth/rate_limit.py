"""Small bounded in-process limiter for account endpoints."""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable


class AttemptLimiter:
    def __init__(
        self,
        *,
        max_keys: int = 4096,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_keys = max_keys
        self.clock = clock
        self._attempts: dict[str, deque[float]] = {}
        self._lock = threading.RLock()

    def retry_after(self, key: str, *, limit: int, window_seconds: int) -> int:
        now = self.clock()
        with self._lock:
            attempts = self._attempts.get(key)
            if attempts is None:
                return 0
            self._prune(attempts, now - window_seconds)
            if not attempts:
                self._attempts.pop(key, None)
                return 0
            if len(attempts) < limit:
                return 0
            return max(1, int(window_seconds - (now - attempts[0])))

    def record(self, key: str) -> None:
        now = self.clock()
        with self._lock:
            if key not in self._attempts and len(self._attempts) >= self.max_keys:
                oldest_key = min(
                    self._attempts,
                    key=lambda item: self._attempts[item][-1],
                )
                self._attempts.pop(oldest_key, None)
            self._attempts.setdefault(key, deque()).append(now)

    def clear(self, key: str) -> None:
        with self._lock:
            self._attempts.pop(key, None)

    @staticmethod
    def _prune(attempts: deque[float], cutoff: float) -> None:
        while attempts and attempts[0] <= cutoff:
            attempts.popleft()
