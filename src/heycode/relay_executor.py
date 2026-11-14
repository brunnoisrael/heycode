"""Executor local das chamadas `bridge-call` do relay (ADR 0044, 0045).

So executa os pares (metodo, caminho) que o Lambda do dono ja usa, com consulta restrita, contra 127.0.0.1 e
com o segredo de controle lido localmente: o relay nunca o conhece. Qualquer outra coisa devolve 403 sem
tocar a ponte. `mode: auto` so passa se o computador tiver liberado (`heycode relay-auto on`).
"""

from collections.abc import Callable
from urllib.parse import parse_qsl, urlsplit

import httpx

# (metodo, caminho) -> chaves de consulta permitidas
ALLOWED: dict[tuple[str, str], set[str]] = {
    ("GET", "/status"): set(),
    ("GET", "/pending"): set(),
    ("GET", "/result"): set(),
    ("GET", "/voice/audit"): {"limit"},
    ("GET", "/voice/commands"): set(),
    ("POST", "/voice/commands/run"): set(),
    ("POST", "/voice/commands/confirm"): set(),
    ("POST", "/voice/commands/cancel"): set(),
    ("POST", "/voice/commands/disable"): set(),
    ("GET", "/voice/projects"): {"offset"},
    ("GET", "/voice/projects/status"): {"project"},
    ("GET", "/voice/projects/resolve"): {"name"},
    ("POST", "/decide"): set(),
    ("POST", "/mode"): set(),
    ("POST", "/dictation"): set(),
    ("POST", "/answer/preview"): set(),
    ("POST", "/answer/confirm"): set(),
    ("POST", "/projects"): set(),
    ("POST", "/confirm"): set(),
    ("POST", "/cancel"): set(),
    ("POST", "/runs/latest/cancel"): set(),
}
MAX_QUERY_VALUE = 200
TIMEOUT = 5.0  # a Alexa tem ~8 s no total

AUTO_NOT_ALLOWED_SPEECH = (
    "Para ligar o modo automático por voz, primeiro ligue-o no computador com o comando heycode relay-auto on."
)


def _denied(error: str = "not_allowed", **extra) -> dict:
    return {"status": 403, "body": {"error": error, **extra}}


class BridgeExecutor:
    def __init__(
        self,
        base_url: str,
        secret: str,
        *,
        auto_allowed: Callable[[], bool],
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._secret = secret
        self._auto_allowed = auto_allowed
        self._transport = transport

    @staticmethod
    def _check(method: str, path: str, body: object) -> tuple[str, str] | None:
        """(caminho, consulta) se a chamada e permitida; None se nao for."""
        if not isinstance(path, str) or "#" in path or "\\" in path:
            return None
        parts = urlsplit(path)
        if parts.scheme or parts.netloc:
            return None
        allowed_keys = ALLOWED.get((method, parts.path))
        if allowed_keys is None:
            return None
        pairs = parse_qsl(parts.query, keep_blank_values=True, strict_parsing=bool(parts.query))
        if any(k not in allowed_keys or len(v) > MAX_QUERY_VALUE for k, v in pairs):
            return None
        if method == "GET" and body is not None:
            return None
        return parts.path, parts.query

    async def __call__(self, payload: dict) -> dict:
        method, path, body = payload.get("method"), payload.get("path"), payload.get("body")
        try:
            checked = self._check(str(method), path, body)  # type: ignore[arg-type]
        except ValueError:  # consulta malformada
            return _denied()
        if checked is None:
            return _denied()
        route, query = checked
        if (method, route) == ("POST", "/mode") and isinstance(body, dict):
            mode = body.get("mode")
            if isinstance(mode, str) and mode.strip().lower() == "auto" and not self._auto_allowed():
                return _denied("auto_not_allowed", speech=AUTO_NOT_ALLOWED_SPEECH)
        url = self._base + route + (f"?{query}" if query else "")
        try:
            async with httpx.AsyncClient(transport=self._transport, timeout=TIMEOUT) as http:
                resp = await http.request(
                    str(method),
                    url,
                    headers={"x-secret": self._secret},
                    json=body if method == "POST" else None,
                )
        except httpx.HTTPError:
            return {"status": 502, "body": {"error": "bridge_unreachable"}}
        try:
            data = resp.json()
        except ValueError:
            data = {"error": "bad_response"}
        return {"status": resp.status_code, "body": data if isinstance(data, dict) else {"value": data}}
