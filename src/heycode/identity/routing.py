"""Roteamento por (conta, instalacao). A conta e o identificador vem da autenticacao, nunca do payload."""

from dataclasses import dataclass

from heycode.identity import IdentityError


@dataclass(frozen=True)
class Installation:
    id: str
    account_id: str
    public_key: str


class Router:
    def __init__(self) -> None:
        self._installations: dict[str, Installation] = {}

    def register(self, installation: Installation) -> None:
        current = self._installations.get(installation.id)
        if current is not None and current.account_id != installation.account_id:
            raise IdentityError("already_registered", "instalacao ja pertence a outra conta")
        self._installations[installation.id] = installation

    def get(self, installation_id: str) -> Installation | None:
        return self._installations.get(installation_id)

    def owns(self, account_id: str, installation_id: str) -> bool:
        inst = self._installations.get(installation_id)
        return inst is not None and inst.account_id == account_id

    def route(self, account_id: str, installation_id: str, envelope: dict) -> Installation:
        """Devolve a instalacao so se for da conta autenticada. `installation_id` do payload e ignorado."""
        inst = self._installations.get(installation_id)
        if inst is None or inst.account_id != account_id:
            raise IdentityError("not_owner", "instalacao nao pertence a esta conta")
        if envelope.get("installation_id") != installation_id:
            raise IdentityError("mismatch", "envelope de outra instalacao")
        return inst
