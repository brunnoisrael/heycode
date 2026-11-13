"""Comandos locais por voz (ADR 0051, 0052): registro validado, casamento e execucao de scripts e webhooks.

Quem define o que roda e SO o computador (`commands.json`, escrito pelo CLI local). Nada falado entra em argv,
URL, corpo ou cabecalho: a fala so escolhe qual comando. Scripts nunca passam por shell.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from heycode.policy.redact import mask_secrets
from heycode.relay.shortcuts import match, normalize
from heycode.supervisor.manager import Supervisor

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


# ---------------------------------------------------------------- execucao

PENDING_TTL = 120.0
MIN_INTERVAL = 3.0
OUTPUT_CAP = 4096
SPEECH_CAP = 200
_MIN_ENV = ("PATH", "HOME", "USERPROFILE", "SYSTEMROOT", "LANG", "TEMP", "TMP", "TMPDIR")


def _short(text: str, cap: int = SPEECH_CAP) -> str:
    return re.sub(r"\s+", " ", mask_secrets(text)).strip()[:cap]


class CommandRunner:
    """Casa a fala, aplica o nivel de risco e executa. Sync: a ponte chama de uma thread do servidor."""

    def __init__(
        self,
        path: Path,
        *,
        secrets: Callable[[], Mapping[str, str]],
        clock: Callable[[], float] = time.time,
        on_event: Callable[[dict], None] | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._path = Path(path)
        self._secrets = secrets
        self._clock = clock
        self._on_event = on_event
        self._transport = transport
        self._lock = threading.Lock()  # uma execucao por vez
        self._pending: dict | None = None
        self._last_run: dict[str, float] = {}

    # --- registro ---
    def _commands(self) -> list[Command]:
        return load(self._path, self._secrets())

    def list(self) -> list[dict]:
        return [summary(c) for c in self._commands()]

    def disable(self, name: str) -> dict:
        """Unico efeito remoto sobre o registro: desligar (ligar e do CLI local)."""
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._commands()  # nao mexe num registro que ja esta invalido
        except (OSError, ValueError, CommandError):
            return {"ok": False, "speech": "Não consegui ler o registro de comandos."}
        for raw in data.get("commands", []):
            if normalize(raw.get("name")) == normalize(name):
                raw["enabled"] = False
                save(self._path, data["commands"], self._secrets())
                if self._pending and normalize(self._pending["name"]) == normalize(name):
                    self._pending = None
                return {"ok": True, "speech": f"Comando {raw['name']} desligado."}
        return {"ok": False, "speech": "Não achei esse comando."}

    # --- fluxo por voz ---
    def start(self, spoken: str) -> dict:
        self._pending = None  # qualquer pedido novo cancela a pendencia anterior
        try:
            commands = self._commands()
        except CommandError:
            return {
                "ok": False,
                "speech": "O registro de comandos tem um erro. Rode heycode command list no computador.",
            }
        if not commands:
            return {"ok": False, "speech": "Nenhum comando local cadastrado. Cadastre um com heycode command add."}
        cmd, why = match_command(spoken, commands)
        if cmd is None:
            speech = (
                "Mais de um comando parece esse. Diga o nome completo."
                if why == "ambiguous"
                else "Não achei esse comando. Diga executar e o nome de um comando cadastrado."
            )
            return {"ok": False, "speech": speech}
        if cmd.risk == "leitura":
            return {**self._execute(cmd), "label": cmd.name}
        self._pending = {
            "name": cmd.name,
            "risk": cmd.risk,
            "hash": definition_hash(cmd),
            "expires": self._clock() + PENDING_TTL,
        }
        what = f" {cmd.description}" if cmd.description else ""
        ask = "Confirma?" if cmd.risk == "confirmar" else "Esse comando exige o seu PIN. Diga aprovar e o PIN."
        return {
            "ok": True,
            "label": cmd.name,
            "pending": {"risk": cmd.risk},
            "speech": f"Vou executar {cmd.name}.{what} {ask}",
        }

    def confirm(self, pin_ok: bool | None = None) -> dict:
        pending = self._pending
        if pending is None or self._clock() > pending["expires"]:
            self._pending = None
            return {"ok": False, "done": False, "speech": "Não há comando aguardando confirmação."}
        try:
            current = {c.name: c for c in self._commands() if c.enabled}.get(pending["name"])
        except CommandError:
            current = None
        if current is None or definition_hash(current) != pending["hash"]:
            self._pending = None
            return {"ok": False, "done": False, "speech": "O comando mudou ou foi desligado. Peça de novo."}
        if pending["risk"] == "pin" and pin_ok is not True:
            return {"ok": False, "done": False, "speech": "Esse comando exige o seu PIN. Diga aprovar e o PIN."}
        self._pending = None
        return {**self._execute(current), "done": True, "label": current.name}

    def pending_risk(self) -> str | None:
        pending = self._pending
        if pending is None or self._clock() > pending["expires"]:
            return None
        return pending["risk"]

    def cancel(self) -> dict:
        had = self._pending is not None
        self._pending = None
        return {"ok": True, "speech": "Cancelado." if had else "Não havia nada para cancelar."}

    # --- execucao ---
    def _execute(self, cmd: Command) -> dict:
        if not self._lock.acquire(blocking=False):
            return {"ok": False, "speech": "Já há um comando em execução. Aguarde terminar."}
        try:
            now = self._clock()
            if now - self._last_run.get(cmd.name, -1e9) < MIN_INTERVAL:
                return {"ok": False, "speech": f"{cmd.name} acabou de rodar. Aguarde um instante."}
            self._last_run[cmd.name] = now
            started = time.monotonic()
            result = self._run_script(cmd) if cmd.type == "script" else self._run_webhook(cmd)
            self._emit(
                {
                    "name": cmd.name,
                    "risk": cmd.risk,
                    "type": cmd.type,
                    "outcome": result["outcome"],
                    "exit_code": result.get("exit_code"),
                    "duration": round(time.monotonic() - started, 2),
                    "t": now,
                }
            )
            return {"ok": result["outcome"] == "ok", "speech": result["speech"]}
        finally:
            self._lock.release()

    def _emit(self, event: dict) -> None:
        if self._on_event is None:
            return
        try:
            self._on_event(event)
        except Exception:  # noqa: BLE001 - o historico nunca derruba a execucao
            pass

    def _run_script(self, cmd: Command) -> dict:
        env = {k: os.environ[k] for k in _MIN_ENV if k in os.environ}
        env.update({k: os.environ[k] for k in cmd.env_pass if k in os.environ})
        argv = list(cmd.argv)
        argv[0] = shutil.which(argv[0]) or argv[0]
        kwargs: dict = {}
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True
        try:
            proc = subprocess.Popen(  # noqa: S603 - argv fixo do registro, sem shell
                argv,
                cwd=cmd.cwd,
                env=env,
                shell=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                **kwargs,
            )
        except OSError:
            return {"outcome": "erro", "speech": f"Não encontrei o programa de {cmd.name}."}
        try:
            output, _ = proc.communicate(timeout=cmd.timeout)
        except subprocess.TimeoutExpired:
            Supervisor._kill_tree(proc)
            try:
                proc.communicate(timeout=5)
            except Exception:  # noqa: BLE001
                pass
            unit = "segundo" if cmd.timeout == 1 else "segundos"
            return {
                "outcome": "timeout",
                "exit_code": None,
                "speech": f"{cmd.name} passou do tempo limite de {cmd.timeout} {unit} e foi interrompido.",
            }
        lines = [ln for ln in (output or "")[-OUTPUT_CAP:].splitlines() if ln.strip()]
        tail = _short(" ".join(lines[-3:]))
        if proc.returncode == 0:
            return {
                "outcome": "ok",
                "exit_code": 0,
                "speech": f"{cmd.name} terminou com sucesso." + (f" Saída: {tail}" if tail else ""),
            }
        return {
            "outcome": "falhou",
            "exit_code": proc.returncode,
            "speech": f"{cmd.name} falhou com código {proc.returncode}." + (f" Saída: {tail}" if tail else ""),
        }

    def _run_webhook(self, cmd: Command) -> dict:
        secrets = self._secrets()
        headers = {}
        for key, value in cmd.headers.items():
            if value.startswith("env:"):
                value = secrets.get(value[4:], "")
                if not value:
                    return {"outcome": "erro", "speech": f"Não consegui chamar {cmd.name}: falta uma credencial local."}
            headers[key] = value
        try:
            with httpx.Client(transport=self._transport, timeout=cmd.timeout, follow_redirects=False) as http:
                resp = http.request(
                    cmd.method, cmd.url, headers=headers, json=cmd.body if cmd.method == "POST" else None
                )
        except httpx.HTTPError:
            return {"outcome": "erro", "speech": f"Não consegui chamar {cmd.name}."}
        body = _short(resp.text)
        code = resp.status_code
        if 200 <= code < 300:
            return {"outcome": "ok", "speech": f"{cmd.name} respondeu {code}." + (f" {body}" if body else "")}
        if 300 <= code < 400:
            return {"outcome": "erro", "speech": f"{cmd.name} respondeu redirecionamento {code}; não segui."}
        return {"outcome": "erro", "speech": f"{cmd.name} respondeu erro {code}." + (f" {body}" if body else "")}
