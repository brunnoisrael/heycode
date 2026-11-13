"""Pareamento por codigo curto (ADR 0030): uso unico, 5 min, limite de tentativas, confirmacao nos dois lados."""

import hashlib
import secrets
from collections.abc import Callable
from dataclasses import dataclass, field

from heycode.identity import IdentityError

ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # sem 0, 1, O, I, L
CODE_LEN = 8
TTL = 300.0
MAX_FAILURES = 5


@dataclass
class Pending:
    id: str
    account_id: str
    public_key: str
    verification: str
    expires_at: float
    confirmed: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class Binding:
    account_id: str
    public_key: str


class PairingService:
    def __init__(self, clock: Callable[[], float]) -> None:
        self._clock = clock
        self._codes: dict[str, tuple[str, float]] = {}  # codigo -> (conta, expira)
        self._pending: dict[str, Pending] = {}
        self._failures: dict[str, list[float]] = {}  # origem -> instantes das falhas

    def issue(self, account_id: str) -> str:
        code = "".join(secrets.choice(ALPHABET) for _ in range(CODE_LEN))
        self._codes[code] = (account_id, self._clock() + TTL)
        return code

    def _locked(self, source: str, now: float) -> bool:
        recent = [t for t in self._failures.get(source, []) if now - t <= TTL]
        self._failures[source] = recent
        return len(recent) >= MAX_FAILURES

    def redeem(self, code: str, public_key: str, source: str) -> Pending:
        now = self._clock()
        if self._locked(source, now):
            raise IdentityError("locked", "muitas tentativas")
        entry = self._codes.pop(code, None)  # uso unico: some ao primeiro resgate
        if entry is None or entry[1] < now:
            self._failures[source].append(now)
            raise IdentityError("invalid_code", "codigo invalido ou expirado")
        account_id = entry[0]
        digest = hashlib.sha256(f"{code}:{public_key}".encode()).digest()
        verification = f"{int.from_bytes(digest[:4], 'big') % 1_000_000:06d}"
        pending = Pending(secrets.token_urlsafe(16), account_id, public_key, verification, now + TTL)
        self._pending[pending.id] = pending
        return pending

    def get_pending(self, pending_id: str) -> Pending | None:
        pending = self._pending.get(pending_id)
        if pending is not None and pending.expires_at < self._clock():
            del self._pending[pending_id]
            return None
        return pending

    def confirm(self, pending_id: str, side: str, account_id: str | None = None) -> Binding | None:
        pending = self._pending.get(pending_id)
        if pending is None:
            raise IdentityError("unknown_pending", "pareamento inexistente ou ja concluido")
        if pending.expires_at < self._clock():
            del self._pending[pending_id]
            raise IdentityError("expired", "pareamento expirado")
        if side not in ("account", "machine"):
            raise IdentityError("invalid_side", "lado invalido")
        if side == "account" and account_id != pending.account_id:
            raise IdentityError("wrong_account", "codigo emitido para outra conta")
        pending.confirmed.add(side)
        if pending.confirmed == {"account", "machine"}:
            del self._pending[pending_id]
            return Binding(pending.account_id, pending.public_key)
        return None
