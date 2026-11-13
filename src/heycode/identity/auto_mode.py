"""Modo auto no cenario multiusuario (ADR 0031): a primeira ativacao exige confirmacao no computador."""

from heycode.identity import IdentityError
from heycode.identity.routing import Router


class AutoMode:
    def __init__(self, router: Router) -> None:
        self._router = router
        self._enabled: set[str] = set()
        self._machine_confirmed: set[str] = set()
        self._devices: set[tuple[str, str, str]] = set()  # (conta, instalacao, dispositivo)

    def _require_owner(self, account_id: str, installation_id: str) -> None:
        if not self._router.owns(account_id, installation_id):
            raise IdentityError("not_owner", "instalacao nao pertence a esta conta")

    def associate_device(self, account_id: str, installation_id: str, device_id: str) -> None:
        self._require_owner(account_id, installation_id)
        self._devices.add((account_id, installation_id, device_id))

    def revoke_device(self, account_id: str, installation_id: str, device_id: str) -> None:
        self._require_owner(account_id, installation_id)
        self._devices.discard((account_id, installation_id, device_id))

    def enable(self, installation_id: str, *, by_account: str, via: str, device_id: str | None = None) -> None:
        self._require_owner(by_account, installation_id)
        if via == "machine":
            self._machine_confirmed.add(installation_id)
        elif via == "voice":
            if device_id is None or (by_account, installation_id, device_id) not in self._devices:
                raise IdentityError("device_not_associated", "dispositivo nao associado a esta instalacao")
            if installation_id not in self._machine_confirmed:
                raise IdentityError("needs_machine_confirmation", "ative o modo auto primeiro no computador")
        else:
            raise IdentityError("invalid_channel", "canal desconhecido")
        self._enabled.add(installation_id)

    def disable(self, installation_id: str, *, by_account: str) -> None:
        self._require_owner(by_account, installation_id)
        self._enabled.discard(installation_id)

    def is_enabled(self, installation_id: str) -> bool:
        return installation_id in self._enabled
