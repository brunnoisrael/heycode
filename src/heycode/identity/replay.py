"""Janela anti-replay: guarda `id` por `ttl` segundos e exige `ts` dentro de +-`skew` do relogio local."""

from heycode.identity import IdentityError


class ReplayWindow:
    def __init__(self, ttl: float = 600, skew: float = 120) -> None:
        self.ttl = ttl
        self.skew = skew
        self._seen: dict[str, float] = {}

    def check(self, msg_id: str, ts: float, now: float) -> None:
        if abs(now - ts) > self.skew:
            raise IdentityError("clock_skew", "ts fora da janela de tolerancia")
        for k in [k for k, seen_at in self._seen.items() if now - seen_at > self.ttl]:
            del self._seen[k]
        if msg_id in self._seen:
            raise IdentityError("replay", "id de mensagem ja visto")
        self._seen[msg_id] = now
