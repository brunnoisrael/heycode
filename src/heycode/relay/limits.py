"""Limites do relay (ADR 0037): taxa por chave com memoria limitada, banimento temporario e cota diaria."""

import math
import time
from collections import OrderedDict, deque
from collections.abc import Callable
from threading import Lock

MAX_KEYS = 20_000


class RateLimiter:
    """Janela deslizante: no maximo `limit` eventos por `window` segundos por chave.

    A memoria tem teto: no maximo `max_keys` chaves; ao estourar, saem as usadas ha mais tempo.
    """

    def __init__(
        self, clock: Callable[[], float], limit: int = 10, window: float = 60.0, max_keys: int = MAX_KEYS
    ) -> None:
        self._clock = clock
        self._limit = limit
        self._window = window
        self._max_keys = max_keys
        self._events: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = Lock()

    def _fresh(self, key: str, now: float) -> deque[float] | None:
        q = self._events.get(key)
        if q is None:
            return None
        while q and now - q[0] > self._window:
            q.popleft()
        if not q:
            del self._events[key]
            return None
        return q

    def allow(self, key: str) -> bool:
        with self._lock:
            now = self._clock()
            q = self._fresh(key, now)
            if q is not None and len(q) >= self._limit:
                return False
            if q is None:
                q = self._events[key] = deque()
                while len(self._events) > self._max_keys:
                    self._events.popitem(last=False)
            else:
                self._events.move_to_end(key)
            q.append(now)
            return True

    def retry_after(self, key: str) -> int:
        """Segundos ate a chave voltar a ter vaga (0 se ja tem)."""
        with self._lock:
            now = self._clock()
            q = self._fresh(key, now)
            if q is None or len(q) < self._limit:
                return 0
            return max(1, math.ceil(q[0] + self._window - now))

    def __len__(self) -> int:
        return len(self._events)


class BanList:
    """Banimento temporario: `points` faltas em `window` segundos bloqueiam a chave por `duration` segundos."""

    def __init__(
        self,
        clock: Callable[[], float],
        points: int = 20,
        window: float = 300.0,
        duration: float = 900.0,
        max_keys: int = MAX_KEYS,
    ) -> None:
        self._clock = clock
        self._duration = duration
        self._max_keys = max_keys
        self._strikes = RateLimiter(clock, limit=points, window=window, max_keys=max_keys)
        self._until: OrderedDict[str, float] = OrderedDict()
        self._lock = Lock()

    def strike(self, key: str) -> None:
        if self._strikes.allow(key):
            return
        with self._lock:
            self._until[key] = self._clock() + self._duration
            self._until.move_to_end(key)
            while len(self._until) > self._max_keys:
                self._until.popitem(last=False)

    def remaining(self, key: str) -> int:
        """Segundos de banimento que faltam (0 se a chave nao esta banida)."""
        with self._lock:
            until = self._until.get(key)
            if until is None:
                return 0
            left = until - self._clock()
            if left <= 0:
                del self._until[key]
                return 0
            return max(1, math.ceil(left))


def day_key(now: float) -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(now))
