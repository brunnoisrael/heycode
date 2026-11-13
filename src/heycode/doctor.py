"""`heycode doctor`: diagnostico por camada, sem expor segredos (spec da P1, secao 5)."""

import json
import shutil
import sqlite3
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from heycode.config import load_env_file

PY_MIN, PY_MAX = (3, 11), (3, 15)  # [min, max)
DEFAULT_URL = "http://127.0.0.1:8765"
MCP_BODY = (
    b'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26",'
    b'"capabilities":{},"clientInfo":{"name":"heycode-doctor","version":"1"}}}'
)


@dataclass
class Check:
    name: str
    layer: str
    status: Literal["ok", "aviso", "falha"]
    detail: str
    fix: str = ""


def _ok(name, layer, detail):
    return Check(name, layer, "ok", detail)


def _call(http, url, *, method="GET", headers=None, body=None, timeout=3):
    """Devolve o codigo HTTP (ou None se nao houve resposta) e o corpo."""
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with http(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, b""
    except (urllib.error.URLError, OSError, ValueError):
        return None, b""


def _value(env, cfg, key):
    return env[key] if key in env else cfg.get(key, "")


def _check_python(py):
    version = f"{py.major}.{py.minor}.{py.micro}"
    if PY_MIN <= (py.major, py.minor) < PY_MAX:
        return _ok("python", "ambiente", f"Python {version}")
    return Check(
        "python",
        "ambiente",
        "falha",
        f"Python {version} fora da faixa 3.11 a 3.14",
        "Instale um Python entre 3.11 e 3.14 e reinstale o heycode.",
    )


def _check_home(env, home, platform):
    if not home.is_dir():
        return Check("diretorio", "ambiente", "falha", f"Diretório não existe: {home}", "Rode: heycode init")
    try:
        with tempfile.NamedTemporaryFile(dir=home):
            pass
    except OSError as exc:
        return Check(
            "diretorio",
            "ambiente",
            "falha",
            f"Sem permissão de escrita em {home}: {exc}",
            "Ajuste as permissões ou defina HEYCODE_HOME para outra pasta.",
        )
    profile = (env.get("USERPROFILE") or "").replace(chr(92), "/").lower()
    if platform == "win32" and profile and not str(home).replace(chr(92), "/").lower().startswith(profile):
        return Check(
            "diretorio",
            "ambiente",
            "aviso",
            f"{home} fica fora do perfil do usuário",
            "Prefira uma pasta dentro do seu perfil, que só o seu usuário acessa.",
        )
    return _ok("diretorio", "ambiente", str(home))


def _check_secrets(env, cfg):
    agent, control = _value(env, cfg, "BRIDGE_SECRET"), _value(env, cfg, "BRIDGE_CONTROL_SECRET")
    problems = []
    for label, value in (("BRIDGE_SECRET", agent), ("BRIDGE_CONTROL_SECRET", control)):
        if not value:
            problems.append(f"{label} ausente")
        elif len(value) < 32:
            problems.append(f"{label} com menos de 32 caracteres")
    if agent and agent == control:
        problems.append("os dois segredos são iguais")
    if problems:
        return Check("segredos", "configuração", "falha", "; ".join(problems), "Rode: heycode init (ou rotate-secret).")
    return _ok("segredos", "configuração", "presentes, com 32+ caracteres e distintos")


def _check_db(env, home):
    path = Path(env["BRIDGE_DB"]) if env.get("BRIDGE_DB") else home / "heycode.db"
    if not path.is_file():
        return Check("banco", "configuração", "aviso", f"{path} ainda não existe; será criado ao iniciar a ponte", "")
    try:
        con = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
        try:
            con.execute("PRAGMA schema_version").fetchone()
        finally:
            con.close()
    except sqlite3.DatabaseError as exc:
        return Check(
            "banco",
            "configuração",
            "falha",
            f"Banco ilegível: {exc}",
            "Restaure um backup ou mova o arquivo e deixe a ponte recriá-lo.",
        )
    return _ok("banco", "configuração", str(path))


def _check_bridge(http, url):
    code, body = _call(http, url + "/health", timeout=2)
    if code is None:
        return Check(
            "ponte",
            "ponte",
            "falha",
            f"A ponte não respondeu em {url}",
            "Inicie com: heycode serve (ou heycode install-service --apply).",
        )
    try:
        healthy = code == 200 and json.loads(body or b"{}").get("ok") is True
    except ValueError:
        healthy = False
    if not healthy:
        return Check(
            "ponte",
            "ponte",
            "falha",
            f"Respondeu em {url}, mas é outro serviço (código {code}), não a ponte",
            "Troque a porta com: heycode serve --port <outra> ou libere a 8765.",
        )
    return _ok("ponte", "ponte", f"saudável em {url}")


def _check_auth(http, url, agent, control):
    fix = "Reinicie a ponte (heycode serve) depois de rotacionar segredos e confira config.env."
    code, _ = _call(http, url + "/status")
    if code != 401:
        return Check("autenticação", "autenticação", "falha", f"/status sem segredo devolveu {code}, esperado 401", fix)
    code, _ = _call(http, url + "/status", headers={"x-secret": control})
    if code != 200:
        return Check("autenticação", "autenticação", "falha", f"segredo de controle recusado ({code})", fix)
    code, _ = _call(http, url + "/status", headers={"x-secret": agent})
    if code == 200:
        return Check(
            "autenticação",
            "autenticação",
            "falha",
            "Os segredos de agente e de controle não estão separados: o de agente abriu a rota de controle",
            fix,
        )
    mcp = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
    code, _ = _call(http, url + "/mcp", method="POST", headers=mcp, body=MCP_BODY)
    if code != 401:
        return Check("autenticação", "autenticação", "falha", f"/mcp sem credencial devolveu {code}, esperado 401", fix)
    code, _ = _call(
        http, url + "/mcp", method="POST", headers={**mcp, "Authorization": f"Bearer {agent}"}, body=MCP_BODY
    )
    if code != 200:
        return Check("autenticação", "autenticação", "falha", f"/mcp com a credencial de agente devolveu {code}", fix)
    return _ok("autenticação", "autenticação", "rotas protegidas exigem segredo e os segredos estão separados")


def _check_hook(env):
    user = Path(env.get("HOME") or env.get("USERPROFILE") or Path.home())
    settings = user / ".claude" / "settings.json"
    example = "Registre o hook conforme docs/claude-settings.example.json."
    try:
        text = settings.read_text(encoding="utf-8")
        json.loads(text)
    except (OSError, ValueError):
        return Check("hook do Claude", "agentes", "aviso", f"{settings} ausente ou ilegível", example)
    if "bridge/hook.py" in text.replace(chr(92) * 2, "/").replace(chr(92), "/"):
        return Check(
            "hook do Claude",
            "agentes",
            "falha",
            "Hook antigo (bridge/hook.py) ainda registrado",
            "Troque o comando por: heycode hook (e heycode hook approve para PermissionRequest).",
        )
    if "heycode hook" in text:
        return _ok("hook do Claude", "agentes", "registrado")
    return Check("hook do Claude", "agentes", "aviso", "Nenhum hook do HeyCode registrado", example)


def _check_public(http, env, cfg):
    url = _value(env, cfg, "BRIDGE_PUBLIC_URL").rstrip("/")
    if not url:
        return Check(
            "url pública",
            "rede externa",
            "aviso",
            "BRIDGE_PUBLIC_URL não definida; só a ponte local foi verificada",
            "Defina BRIDGE_PUBLIC_URL=https://seu-endereco para testar o caminho externo.",
        )
    code, _ = _call(http, url + "/health", timeout=5)
    if code == 200:
        return _ok("url pública", "rede externa", f"{url} alcançável")
    return Check(
        "url pública",
        "rede externa",
        "falha",
        f"{url}/health não respondeu 200 ({code})",
        "Confira o túnel/DNS e se a ponte está no ar.",
    )


def run_checks(env, home, *, http=None, which=None, py_version=None, platform=None):
    http = http or urllib.request.urlopen
    which = which or shutil.which
    py_version = py_version or sys.version_info
    platform = platform or sys.platform
    home = Path(home)
    cfg = load_env_file(home / "config.env")
    url = (_value(env, cfg, "BRIDGE_URL") or DEFAULT_URL).rstrip("/")
    checks = [_check_python(py_version), _check_home(env, home, platform)]
    secrets_check = _check_secrets(env, cfg)
    checks += [secrets_check, _check_db(env, home)]
    bridge = _check_bridge(http, url)
    checks.append(bridge)
    if bridge.status == "ok" and secrets_check.status == "ok":
        checks.append(
            _check_auth(http, url, _value(env, cfg, "BRIDGE_SECRET"), _value(env, cfg, "BRIDGE_CONTROL_SECRET"))
        )
    else:
        checks.append(
            Check("autenticação", "autenticação", "aviso", "pulada: depende da ponte no ar e de segredos válidos", "")
        )
    for agent in ("claude", "codex", "aider"):
        path = which(agent)
        if path:
            checks.append(_ok(agent, "agentes", f"encontrado: {path}"))
        else:
            checks.append(
                Check(
                    agent,
                    "agentes",
                    "aviso",
                    "não encontrado no PATH",
                    f"Instale o {agent} se for usá-lo com o HeyCode.",
                )
            )
    checks.append(_check_hook(env))
    checks.append(_check_public(http, env, cfg))
    checks.append(
        Check(
            "alexa",
            "alexa",
            "aviso",
            "não é verificável localmente",
            "Teste no simulador do console de desenvolvimento da Alexa e com o Echo real.",
        )
    )
    return checks
