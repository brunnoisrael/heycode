"""Cliente local do relay (spec P3): conexao de saida persistente, reconexao com backoff, falha aberta.

Nada aqui pode travar ou quebrar um agente: `run_forever` nunca levanta, e um erro do tratador de pedidos
vira uma mensagem `error` para o relay, sem derrubar a sessao.
"""

import asyncio
import inspect
import json
import random
import time
from collections.abc import Awaitable, Callable
from contextlib import suppress
from pathlib import Path
from urllib.parse import urlparse

from heycode.protocol import ProtocolError, validate
from heycode.protocol.outbound import build_envelope

BACKOFF_MIN = 1.0
BACKOFF_MAX = 60.0
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def backoff_delay(attempt: int, rand: Callable[[], float] = random.random) -> float:
    """1 s, 2 s, 4 s... ate 60 s, com jitter de +-20% (sempre dentro de [1, 60])."""
    base = min(BACKOFF_MAX, BACKOFF_MIN * (2 ** min(attempt, 10)))
    return min(BACKOFF_MAX, max(BACKOFF_MIN, base * (0.8 + 0.4 * rand())))


def check_relay_url(url: str) -> None:
    """Sem TLS so para o proprio computador: o relay e autenticado pelo certificado (ADR 0038)."""
    parsed = urlparse(url)
    if parsed.scheme == "wss" or (parsed.scheme == "ws" and parsed.hostname in _LOCAL_HOSTS):
        return
    raise ValueError("o endereco do relay deve usar wss:// (ws:// so para localhost)")


def default_connect(url: str):
    from websockets.asyncio.client import connect

    return connect(url)


Handler = Callable[[dict], "dict | Awaitable[dict]"]


class RelayClient:
    def __init__(
        self,
        url: str,
        installation_id: str,
        private_key,
        handler: Handler,
        *,
        clock: Callable[[], float] = time.time,
        connect: Callable = default_connect,
        sleep: Callable[[float], Awaitable] | None = None,
    ) -> None:
        check_relay_url(url)
        self._url = url
        self._iid = installation_id
        self._key = private_key
        self._handler = handler
        self._clock = clock
        self._connect = connect
        self._sleep = sleep or asyncio.sleep
        self._stopped = False
        self._acked = False

    def stop(self) -> None:
        self._stopped = True

    def _envelope(self, type_: str, payload: dict) -> str:
        env = build_envelope(type_, payload, installation_id=self._iid, private_key=self._key, now=self._clock())
        return json.dumps(env)

    async def run_forever(self) -> None:
        attempt = 0
        while not self._stopped:
            self._acked = False
            try:
                async with self._connect(self._url) as ws:
                    await self._session(ws)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - falha aberta: qualquer erro vira nova tentativa
                pass
            if self._stopped:
                break
            if self._acked:
                attempt = 0
            await self._sleep(backoff_delay(attempt))
            attempt += 1

    async def _session(self, ws) -> None:
        await ws.send(self._envelope("status", {"state": "idle"}))
        ack = json.loads(await ws.recv())
        if ack.get("type") != "status":
            raise ConnectionError("handshake recusado pelo relay")
        self._acked = True
        while not self._stopped:
            try:
                msg = json.loads(await ws.recv())
                validate(msg)
            except (ValueError, ProtocolError):
                continue  # quadro malformado do relay: ignora
            if msg["type"] == "instruction":
                await self._handle(ws, msg)

    async def _handle(self, ws, msg: dict) -> None:
        request_id = msg["id"]
        try:
            result = self._handler(msg["payload"])
            if inspect.isawaitable(result):
                result = await result
            reply = self._envelope("run-result", {**result, "in_reply_to": request_id})
        except Exception as exc:  # noqa: BLE001 - erro do agente nao derruba a sessao
            reply = self._envelope(
                "error", {"code": "handler_failed", "message": type(exc).__name__, "in_reply_to": request_id}
            )
        await ws.send(reply)


# --- pareamento ---


class PairingError(Exception):
    pass


def relay_config_path(home: Path) -> Path:
    return home / "relay.json"


def load_relay_config(home: Path) -> dict | None:
    path = relay_config_path(home)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def ws_url(relay_url: str) -> str:
    parsed = urlparse(relay_url)
    scheme = {"https": "wss", "http": "ws"}.get(parsed.scheme, parsed.scheme)
    return f"{scheme}://{parsed.netloc}/v1/connect"


def pair_with_relay(
    relay_url: str,
    code: str,
    name: str,
    home: Path,
    *,
    http,
    confirm: Callable[[str], bool],
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.time,
    timeout: float = 300.0,
    force: bool = False,
) -> str:
    """Resgata o codigo, mostra o codigo de verificacao, confirma no computador e espera a conta confirmar."""
    from heycode.identity.keys import generate_keypair

    parsed = urlparse(relay_url)
    if parsed.scheme != "https" and parsed.hostname not in _LOCAL_HOSTS:
        raise PairingError("o endereco do relay deve usar https:// (http:// so para localhost)")
    base = relay_url.rstrip("/")
    try:
        public_key = generate_keypair(home, force=force)
    except FileExistsError as exc:
        raise PairingError("este computador ja tem uma identidade; use --force para parear de novo") from exc
    resp = http.post(f"{base}/v1/pair/redeem", json={"code": code, "public_key": public_key, "name": name})
    if resp.status_code != 200:
        raise PairingError(f"codigo recusado pelo relay ({resp.json().get('detail', resp.status_code)})")
    data = resp.json()
    pending_id = data["pending_id"]
    if not confirm(data["verification"]):
        raise PairingError("pareamento cancelado")
    done = http.post(f"{base}/v1/pair/machine-confirm", json={"pending_id": pending_id})
    if done.status_code != 200:
        raise PairingError(f"o relay recusou a confirmacao ({done.json().get('detail', done.status_code)})")
    deadline = clock() + timeout
    state = done.json()
    while state.get("state") != "done":
        if clock() > deadline:
            raise PairingError("tempo esgotado esperando a confirmacao na conta")
        sleep(2.0)
        poll = http.get(f"{base}/v1/pair/{pending_id}")
        if poll.status_code != 200:
            raise PairingError("pareamento expirou ou foi recusado")
        state = poll.json()
    relay_config_path(home).write_text(
        json.dumps({"relay_url": base, "installation_id": state["installation_id"]}), encoding="utf-8"
    )
    with suppress(OSError):
        relay_config_path(home).chmod(0o600)
    return state["installation_id"]
