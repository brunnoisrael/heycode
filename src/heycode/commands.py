"""Comandos locais por voz (ADR 0051, 0052): registro validado, casamento e execucao de scripts e webhooks.

Quem define o que roda e SO o computador (`commands.json`, escrito pelo CLI local). Nada falado entra em argv,
URL, corpo ou cabecalho: a fala so escolhe qual comando. Scripts nunca passam por shell.
"""

import hashlib
import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from heycode.relay.shortcuts import match, normalize

VERSION = 1
MAX_COMMANDS = 50
RISKS = ("leitura", "confirmar", "pin")
TYPES = ("script", "webhook")
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
ENV_NAME = re.compile(r"^[A-Z_][A-Z0-9_]*$")
HEADER_NAME = re.compile(r"^[A-Za-z0-9-]{1,64}$")

_COMMON = {"name", "aliases", "type", "risk", "enabled", "description"}
_SCRIPT = {"argv", "cwd", "timeout", "env_pass"}
_WEBHOOK = {"url", "method", "body", "headers", "timeout"}


class CommandError(ValueError):
    """Registro invalido: a mensagem diz qual comando e o que corrigir."""


@dataclass(frozen=True)
class Command:
    name: str
    type: str
    risk: str
    aliases: tuple[str, ...] = ()
    enabled: bool = True
    description: str = ""
    argv: tuple[str, ...] = ()
    cwd: str | None = None
    timeout: int = 60
    env_pass: tuple[str, ...] = ()
    url: str = ""
    method: str = "GET"
    body: dict | None = None
    headers: dict = field(default_factory=dict)

    def as_match_dict(self) -> dict:
        return {"id": self.name, "name": self.name, "aliases": list(self.aliases), "enabled": self.enabled}


def _fail(name: str, message: str) -> CommandError:
    return CommandError(f"comando {name!r}: {message}")


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _parse_one(raw: object, env: Mapping[str, str], index: int) -> Command:
    if not isinstance(raw, dict):
        raise CommandError(f"comando #{index + 1}: deve ser um objeto")
    name = raw.get("name")
    if not isinstance(name, str) or not 2 <= len(name.strip()) <= 40 or len(normalize(name)) < 2:
        raise CommandError(f"comando #{index + 1}: nome com 2 a 40 caracteres falaveis")
    name = name.strip()
    kind = raw.get("type")
    if kind not in TYPES:
        raise _fail(name, f"type deve ser um de {TYPES}")
    unknown = set(raw) - _COMMON - (_SCRIPT if kind == "script" else _WEBHOOK)
    if unknown:
        raise _fail(name, f"campos desconhecidos ou fora do tipo: {sorted(unknown)}")
    if raw.get("risk") not in RISKS:
        raise _fail(name, f"risk deve ser um de {RISKS}")
    enabled = raw.get("enabled", True)
    if not isinstance(enabled, bool):
        raise _fail(name, "enabled deve ser true ou false")
    description = raw.get("description", "")
    if not isinstance(description, str) or len(description) > 200:
        raise _fail(name, "description deve ter ate 200 caracteres")
    aliases = raw.get("aliases", [])
    if (
        not isinstance(aliases, list)
        or len(aliases) > 5
        or any(not isinstance(a, str) or not 2 <= len(a.strip()) <= 40 or len(normalize(a)) < 2 for a in aliases)
    ):
        raise _fail(name, "aliases: ate 5 textos de 2 a 40 caracteres falaveis")
    base = {
        "name": name,
        "type": kind,
        "risk": raw["risk"],
        "aliases": tuple(a.strip() for a in aliases),
        "enabled": enabled,
        "description": description,
    }
    if kind == "script":
        return _parse_script(name, raw, base)
    return _parse_webhook(name, raw, base, env)


def _parse_script(name: str, raw: dict, base: dict) -> Command:
    argv = raw.get("argv")
    if (
        not isinstance(argv, list)
        or not 1 <= len(argv) <= 32
        or any(not isinstance(a, str) or len(a) > 500 for a in argv)
        or not argv[0].strip()
    ):
        raise _fail(name, "argv deve ser uma lista de 1 a 32 textos (o primeiro e o programa; nunca um shell)")
    cwd = raw.get("cwd")
    if cwd is not None and (not isinstance(cwd, str) or not os.path.isabs(cwd) or not os.path.isdir(cwd)):
        raise _fail(name, "cwd deve ser um diretorio absoluto que exista")
    timeout = raw.get("timeout", 60)
    if not _is_int(timeout) or not 1 <= timeout <= 300:
        raise _fail(name, "timeout deve ser um inteiro de 1 a 300")
    env_pass = raw.get("env_pass", [])
    if not isinstance(env_pass, list) or any(not isinstance(n, str) or not ENV_NAME.match(n) for n in env_pass):
        raise _fail(name, "env_pass: nomes de variavel em MAIUSCULAS")
    return Command(**base, argv=tuple(argv), cwd=cwd, timeout=timeout, env_pass=tuple(env_pass))


def _parse_webhook(name: str, raw: dict, base: dict, env: Mapping[str, str]) -> Command:
    url = raw.get("url")
    method = raw.get("method", "GET")
    if method not in ("GET", "POST"):
        raise _fail(name, "method deve ser GET ou POST")
    if not isinstance(url, str):
        raise _fail(name, "url obrigatoria")
    try:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        parts.port  # noqa: B018 - valida a porta
    except ValueError as exc:
        raise _fail(name, "url invalida") from exc
    if (
        not host
        or parts.username is not None
        or parts.password is not None
        or parts.fragment
        or not (parts.scheme == "https" or (parts.scheme == "http" and host in LOCAL_HOSTS))
    ):
        raise _fail(name, "url deve ser https (http so para localhost), sem usuario nem fragmento")
    if method == "POST" and base["risk"] == "leitura":
        raise _fail(name, "webhook POST muda estado e nunca pode ter risk leitura")
    body = raw.get("body")
    if body is not None and (method != "POST" or not isinstance(body, dict)):
        raise _fail(name, "body so existe em POST e deve ser um objeto JSON")
    headers = raw.get("headers", {})
    if not isinstance(headers, dict):
        raise _fail(name, "headers deve ser um objeto")
    for key, value in headers.items():
        if not isinstance(key, str) or not HEADER_NAME.match(key) or not isinstance(value, str):
            raise _fail(name, f"cabecalho invalido: {key!r}")
        if value.startswith("env:") and not env.get(value[4:]):
            raise _fail(name, f"cabecalho {key}: a variavel {value[4:]!r} nao existe no config.env")
    timeout = raw.get("timeout", 10)
    if not _is_int(timeout) or not 1 <= timeout <= 30:
        raise _fail(name, "timeout deve ser um inteiro de 1 a 30")
    return Command(**base, url=url, method=method, body=body, headers=dict(headers), timeout=timeout)


def parse_registry(data: object, env: Mapping[str, str] | None = None) -> list[Command]:
    if not isinstance(data, dict) or data.get("version") != VERSION or set(data) - {"version", "commands"}:
        raise CommandError(f"registro: esperado {{'version': {VERSION}, 'commands': [...]}}")
    raw = data.get("commands")
    if not isinstance(raw, list):
        raise CommandError("registro: commands deve ser uma lista")
    if len(raw) > MAX_COMMANDS:
        raise CommandError(f"registro: no maximo {MAX_COMMANDS} comandos")
    commands = [_parse_one(item, env or {}, i) for i, item in enumerate(raw)]
    seen: dict[str, str] = {}
    for c in commands:
        for spoken in (c.name, *c.aliases):
            key = normalize(spoken)
            if key in seen:
                raise CommandError(f"{c.name!r} e {seen[key]!r} soam igual para a Alexa ({spoken!r})")
            seen[key] = c.name
    return commands


def load(path: Path, env: Mapping[str, str] | None = None) -> list[Command]:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise CommandError(f"{path}: JSON invalido ({exc})") from exc
    return parse_registry(data, env)


def save(path: Path, commands: list[dict], env: Mapping[str, str] | None = None) -> None:
    """Valida e grava de forma atomica (nunca deixa um registro pela metade)."""
    data = {"version": VERSION, "commands": commands}
    parse_registry(data, env)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    try:
        tmp.chmod(0o600)
    except OSError:
        pass
    os.replace(tmp, path)


def summary(c: Command) -> dict:
    """O unico que sai da maquina: nunca argv, url, cabecalhos, corpo ou cwd."""
    return {
        "name": c.name,
        "aliases": list(c.aliases),
        "type": c.type,
        "risk": c.risk,
        "enabled": c.enabled,
        "description": c.description,
    }


def definition_hash(c: Command) -> str:
    blob = json.dumps(
        {
            "name": c.name,
            "type": c.type,
            "risk": c.risk,
            "argv": c.argv,
            "cwd": c.cwd,
            "timeout": c.timeout,
            "env_pass": c.env_pass,
            "url": c.url,
            "method": c.method,
            "body": c.body,
            "headers": c.headers,
        },
        sort_keys=True,
    )
    return hashlib.sha256(blob.encode()).hexdigest()


def match_command(spoken: str, commands: list[Command]) -> tuple[Command | None, str]:
    """(comando, "ok") | (None, "none"|"ambiguous"). So comandos ligados entram."""
    by_name = {c.name: c for c in commands}
    found, why = match(spoken, [c.as_match_dict() for c in commands])
    return (by_name[found["name"]], why) if found else (None, why)
