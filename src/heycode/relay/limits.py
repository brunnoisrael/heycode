"""Limites do relay (ADR 0037): taxa por origem e cota diaria por conta."""

import time
from collections import defaultdict, deque
from collections.abc import Callable


class RateLimiter:
    """Janela deslizante: no maximo `limit` eventos por `window` segundos por chave."""

    def __init__(self, clock: Callable[[], float], limit: int = 10, window: float = 60.0) -> None:
        self._clock = clock
        self._limit = limit
        self._window = window
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = self._clock()
        q = self._events[key]
        while q and now - q[0] > self._window:
            q.popleft()
        if len(q) >= self._limit:
            return False
        q.append(now)
        return True


def day_key(now: float) -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(now))
