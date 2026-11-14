"""Hub de conexoes das instalacoes e dos pedidos em andamento (ADR 0035: instancia unica, em memoria)."""

import asyncio
from collections import OrderedDict
from dataclasses import dataclass, field

MAX_TRACKED = 1000
CLOSE_REPLACED = 4000


@dataclass
class _Request:
    installation_id: str
    account_id: str
    future: asyncio.Future
    result: dict | None = field(default=None)


class Hub:
    def __init__(self) -> None:
        self._conns: dict[str, object] = {}
        self._requests: OrderedDict[str, _Request] = OrderedDict()

    def is_online(self, installation_id: str) -> bool:
        return installation_id in self._conns

    async def attach(self, installation_id: str, ws) -> None:
        old = self._conns.get(installation_id)
        self._conns[installation_id] = ws
        if old is not None and old is not ws:
            try:
                await old.close(code=CLOSE_REPLACED)
            except Exception:  # noqa: BLE001 - a conexao antiga pode ja ter caido
                pass

    def detach(self, installation_id: str, ws) -> None:
        if self._conns.get(installation_id) is ws:
            del self._conns[installation_id]

    async def disconnect(self, installation_id: str) -> None:
        ws = self._conns.pop(installation_id, None)
        if ws is not None:
            try:
                await ws.close(code=4401)
            except Exception:  # noqa: BLE001
                pass

    async def request(
        self, installation_id: str, account_id: str, envelope: dict, timeout: float
    ) -> tuple[str, dict | None]:
        """Envia o pedido e espera ate `timeout`: ("offline"|"done"|"pending", resultado)."""
        ws = self._conns.get(installation_id)
        if ws is None:
            return "offline", None
        req = _Request(installation_id, account_id, asyncio.get_running_loop().create_future())
        self._requests[envelope["id"]] = req
        while len(self._requests) > MAX_TRACKED:
            self._requests.popitem(last=False)
        try:
            await ws.send_json(envelope)
        except Exception:  # noqa: BLE001 - conexao morta conta como offline
            self._requests.pop(envelope["id"], None)
            self._conns.pop(installation_id, None)
            return "offline", None
        try:
            await asyncio.wait_for(asyncio.shield(req.future), timeout)
        except TimeoutError:
            return "pending", None
        return "done", req.result

    def resolve(self, installation_id: str, request_id: str, payload: dict) -> bool:
        """So a instalacao que recebeu o pedido pode resolve-lo."""
        req = self._requests.get(request_id)
        if req is None or req.installation_id != installation_id:
            return False
        req.result = payload
        if not req.future.done():
            req.future.set_result(payload)
        return True

    def result_for(self, account_id: str, request_id: str) -> dict | None:
        """None se o pedido nao existe ou nao e desta conta; senao {"state", "result"}."""
        req = self._requests.get(request_id)
        if req is None or req.account_id != account_id:
            return None
        if req.result is None:
            return {"state": "pending"}
        return {"state": "done", "result": req.result}
