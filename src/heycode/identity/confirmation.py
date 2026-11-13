"""Confirmacao atada a (operacao, destino, instalacao), de uso unico e com validade (spec §5)."""

import secrets
from collections.abc import Callable

from heycode.identity import IdentityError


class ConfirmationStore:
    def __init__(self, clock: Callable[[], float], ttl: float = 300.0) -> None:
        self._clock = clock
        self._ttl = ttl
        self._items: dict[str, tuple[str, str, str, float]] = {}

    def bind(self, operation: str, destination: str, installation_id: str) -> str:
        cid = secrets.token_urlsafe(16)
        self._items[cid] = (operation, destination, installation_id, self._clock() + self._ttl)
        return cid

    def _purge(self) -> None:
        now = self._clock()
        for k in [k for k, v in self._items.items() if v[3] < now]:
            del self._items[k]

    def pending_count(self) -> int:
        self._purge()
        return len(self._items)

    def consume(self, cid: str, operation: str, destination: str, installation_id: str) -> None:
        item = self._items.get(cid)
        if item is None:
            raise IdentityError("unknown_confirmation", "confirmacao inexistente ou ja usada")
        if item[3] < self._clock():
            del self._items[cid]
            raise IdentityError("expired", "confirmacao expirada")
        if (item[0], item[1], item[2]) != (operation, destination, installation_id):
            raise IdentityError("mismatch", "confirmacao nao vale para esta operacao ou destino")
        del self._items[cid]
