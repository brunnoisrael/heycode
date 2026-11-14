"""Instalacoes revogadas. O relay e a maquina consultam antes de aceitar qualquer envelope."""


class Registry:
    def __init__(self) -> None:
        self._revoked: set[str] = set()

    def revoke(self, installation_id: str) -> None:
        self._revoked.add(installation_id)

    def is_revoked(self, installation_id: str) -> bool:
        return installation_id in self._revoked
