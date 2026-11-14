import json
import sqlite3
import urllib.error
from collections import namedtuple

import pytest

from heycode.cli import main
from heycode.config import init_home, load_env_file
from heycode.doctor import Check, run_checks

PY = namedtuple("PY", "major minor micro")
AGENT = "a" * 64
CONTROL = "c" * 64


class Resp:
    def __init__(self, code=200, body=b'{"ok": true}'):
        self.status = code
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class Bridge:
    """Ponte falsa: reproduz /health, /status (so controle) e /mcp (so agente)."""

    def __init__(self, up=True, health_body=b'{"ok": true}', agent=AGENT, control=CONTROL, leaky=False):
        self.up, self.health_body, self.agent, self.control, self.leaky = up, health_body, agent, control, leaky
        self.calls = []

    def __call__(self, req, timeout=None):
        url = req.full_url if hasattr(req, "full_url") else req
        headers = {k.lower(): v for k, v in (req.headers.items() if hasattr(req, "headers") else [])}
        self.calls.append((req.get_method() if hasattr(req, "get_method") else "GET", url, headers))
        if not self.up:
            raise urllib.error.URLError(ConnectionRefusedError())
        path = "/" + url.split("/", 3)[3] if url.count("/") >= 3 else "/"
        if path.startswith("/health"):
            return Resp(200, self.health_body)
        if path.startswith("/status"):
            secret = headers.get("x-secret")
            ok = secret == self.control or (self.leaky and secret == self.agent)
            if ok:
                return Resp(200, b"{}")
            raise urllib.error.HTTPError(url, 401, "unauthorized", {}, None)
        if path.startswith("/mcp"):
            if headers.get("authorization") == f"Bearer {self.agent}":
                return Resp(200, b"{}")
            raise urllib.error.HTTPError(url, 401, "unauthorized", {}, None)
        raise urllib.error.HTTPError(url, 404, "nf", {}, None)


@pytest.fixture
def home(tmp_path):
    h = tmp_path / "heycode"
    init_home(h)
    (h / "config.env").write_text(
        f"BRIDGE_SECRET={AGENT}"
        + chr(10)
        + f"BRIDGE_CONTROL_SECRET={CONTROL}"
        + chr(10)
        + "BRIDGE_PIN=123456"
        + chr(10)
        + "",
        encoding="utf-8",
    )
    return h


def env_for(home, **extra):
    values = load_env_file(home / "config.env")
    return {
        "HEYCODE_HOME": str(home),
        "HOME": str(home.parent),
        "BRIDGE_URL": "http://127.0.0.1:8765",
        **values,
        **extra,
    }


def by_name(checks):
    return {c.name: c for c in checks}


PY_ATUAL = PY(3, 12, 1)


def run(home, bridge=None, which=lambda n: f"/bin/{n}", py=PY_ATUAL, **extra_env):
    env = env_for(home, **extra_env)
    return run_checks(env, home, http=bridge or Bridge(), which=which, py_version=py, platform="linux")


def test_tudo_certo_nao_tem_falha(home):
    checks = run(home)
    assert not [c for c in checks if c.status == "falha"], [(c.name, c.detail) for c in checks if c.status == "falha"]
    assert all(isinstance(c, Check) for c in checks)


@pytest.mark.parametrize(
    "py,ok", [(PY(3, 10, 0), False), (PY(3, 11, 0), True), (PY(3, 14, 2), True), (PY(3, 15, 0), False)]
)
def test_faixa_de_python(home, py, ok):
    c = by_name(run(home, py=py))["python"]
    assert (c.status == "ok") is ok and c.layer == "ambiente"


def test_diretorio_inexistente_falha_e_orienta_o_init(tmp_path):
    h = tmp_path / "nao-existe"
    checks = run_checks(
        {"HEYCODE_HOME": str(h)},
        h,
        http=Bridge(up=False),
        which=lambda n: None,
        py_version=PY(3, 12, 0),
        platform="linux",
    )
    c = by_name(checks)["diretorio"]
    assert c.status == "falha" and "heycode init" in c.fix


@pytest.mark.parametrize(
    "agent,control,expected",
    [
        ("", CONTROL, "falha"),
        (AGENT, "", "falha"),
        ("curto", CONTROL, "falha"),
        (AGENT, "curto", "falha"),
        (AGENT, AGENT, "falha"),
    ],
)
def test_segredos_ausentes_curtos_ou_iguais_falham(home, agent, control, expected):
    c = by_name(run(home, BRIDGE_SECRET=agent, BRIDGE_CONTROL_SECRET=control))["segredos"]
    assert c.status == expected and c.layer == "configuração"


def test_banco_inexistente_e_aviso_e_corrompido_e_falha(home):
    assert by_name(run(home))["banco"].status == "aviso"
    (home / "heycode.db").write_bytes(b"isto nao e sqlite " * 50)
    assert by_name(run(home))["banco"].status == "falha"


def test_banco_valido_e_ok(home):
    sqlite3.connect(home / "heycode.db").execute("create table t(x)").connection.close()
    assert by_name(run(home))["banco"].status == "ok"


def test_ponte_fora_do_ar_falha_na_camada_ponte_e_pula_a_autenticacao(home):
    checks = by_name(run(home, bridge=Bridge(up=False)))
    assert checks["ponte"].status == "falha" and checks["ponte"].layer == "ponte"
    assert "install-service" in checks["ponte"].fix or "serve" in checks["ponte"].fix
    assert checks["autenticação"].status == "aviso"


def test_porta_ocupada_por_outro_servico_e_distinta_de_ponte_saudavel(home):
    other = by_name(run(home, bridge=Bridge(health_body=b"<html>outro servico</html>")))["ponte"]
    assert other.status == "falha" and "outro serviço" in other.detail.lower()


def test_autenticacao_ok_quando_os_segredos_estao_separados(home):
    c = by_name(run(home))["autenticação"]
    assert c.status == "ok"


def test_segredo_de_agente_aceito_na_rota_de_controle_e_falha(home):
    c = by_name(run(home, bridge=Bridge(leaky=True)))["autenticação"]
    assert c.status == "falha" and "separa" in c.detail.lower()


def test_rota_protegida_sem_segredo_deve_dar_401(home):
    class Open(Bridge):
        def __call__(self, req, timeout=None):
            if "/status" in req.full_url:
                return Resp(200, b"{}")
            return super().__call__(req, timeout)

    assert by_name(run(home, bridge=Open()))["autenticação"].status == "falha"


def test_agente_ausente_no_path_e_aviso(home):
    checks = by_name(run(home, which=lambda n: None))
    for name in ("claude", "codex", "aider"):
        assert checks[name].status == "aviso" and checks[name].layer == "agentes"


def _claude_settings(home, text):
    d = home.parent / ".claude"
    d.mkdir(exist_ok=True)
    (d / "settings.json").write_text(text, encoding="utf-8")


def test_hook_antigo_do_bridge_e_detectado_e_orienta(home):
    _claude_settings(home, json.dumps({"hooks": {"Stop": [{"hooks": [{"command": "python ~/x/bridge/hook.py"}]}]}}))
    c = by_name(run(home))["hook do Claude"]
    assert c.status == "falha" and "heycode hook" in c.fix


def test_hook_novo_e_ok_e_ausente_e_aviso(home):
    assert by_name(run(home))["hook do Claude"].status == "aviso"
    _claude_settings(home, json.dumps({"hooks": {"Stop": [{"hooks": [{"command": "heycode hook"}]}]}}))
    assert by_name(run(home))["hook do Claude"].status == "ok"


def test_settings_ilegivel_do_claude_nao_quebra_o_doctor(home):
    _claude_settings(home, "{ isto nao e json")
    assert by_name(run(home))["hook do Claude"].status == "aviso"


def test_rede_externa_sem_url_e_aviso_e_com_url_e_ok(home):
    assert by_name(run(home))["url pública"].status == "aviso"
    bridge = Bridge()
    c = by_name(run(home, bridge=bridge, BRIDGE_PUBLIC_URL="https://ponte.exemplo.dev"))["url pública"]
    assert c.status == "ok" and any("ponte.exemplo.dev/health" in call[1] for call in bridge.calls)


def test_url_publica_inalcancavel_falha(home):
    class Mixed(Bridge):
        def __call__(self, req, timeout=None):
            if "exemplo.dev" in req.full_url:
                raise urllib.error.URLError("sem rota")
            return super().__call__(req, timeout)

    assert (
        by_name(run(home, bridge=Mixed(), BRIDGE_PUBLIC_URL="https://ponte.exemplo.dev"))["url pública"].status
        == "falha"
    )


def test_alexa_e_sempre_aviso(home):
    c = by_name(run(home))["alexa"]
    assert c.status == "aviso" and c.layer == "alexa" and "console" in c.fix.lower()


def test_nenhuma_saida_contem_segredos(home):
    checks = run(home, bridge=Bridge(leaky=True))
    secrets = [AGENT, CONTROL, *load_env_file(home / "config.env").values()]
    text = json.dumps([c.__dict__ for c in checks], ensure_ascii=False)
    assert all(s not in text for s in secrets)


# ----------------------------------------------------------------------------- CLI


def test_cli_doctor_json_e_valido_e_sai_1_com_falha(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HEYCODE_HOME", str(tmp_path / "vazio"))
    monkeypatch.setenv("BRIDGE_URL", "http://127.0.0.1:1")  # hermetico: nao fala com uma ponte real
    assert main(["doctor", "--json"]) == 1
    data = json.loads(capsys.readouterr().out)
    assert {"name", "layer", "status", "detail", "fix"} <= set(data[0])
    assert any(d["status"] == "falha" for d in data)


def test_cli_doctor_json_pode_ser_lido_com_utf8_no_windows(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HEYCODE_HOME", str(tmp_path / "vazio"))
    monkeypatch.setenv("BRIDGE_URL", "http://127.0.0.1:1")
    main(["doctor", "--json"])
    text = capsys.readouterr().out
    assert text.isascii()
    assert json.loads(text)[0]["name"] == "python"


def test_cli_doctor_texto_mostra_camadas(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HEYCODE_HOME", str(tmp_path / "vazio"))
    monkeypatch.setenv("BRIDGE_URL", "http://127.0.0.1:1")
    main(["doctor"])
    out = capsys.readouterr().out
    for layer in ("ambiente", "configuração", "ponte", "autenticação", "agentes", "alexa"):
        assert layer in out


def test_cli_doctor_sai_0_quando_nao_ha_falha(tmp_path, monkeypatch, capsys):
    h = tmp_path / "h"
    init_home(h)
    values = load_env_file(h / "config.env")
    monkeypatch.setenv("HEYCODE_HOME", str(h))
    monkeypatch.setenv("HOME", str(tmp_path))
    for key in ("BRIDGE_SECRET", "BRIDGE_CONTROL_SECRET", "BRIDGE_URL", "BRIDGE_PUBLIC_URL", "BRIDGE_DB"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(
        "heycode.doctor.urllib.request.urlopen",
        Bridge(agent=values["BRIDGE_SECRET"], control=values["BRIDGE_CONTROL_SECRET"]),
    )
    monkeypatch.setattr("heycode.doctor.shutil.which", lambda n: f"/bin/{n}")
    assert main(["doctor"]) == 0


def test_path_do_home_aceita_acentos_e_espacos(tmp_path):
    h = tmp_path / "João Silva" / "heycode"
    init_home(h)
    values = load_env_file(h / "config.env")
    bridge = Bridge(agent=values["BRIDGE_SECRET"], control=values["BRIDGE_CONTROL_SECRET"])
    assert not [
        c
        for c in run_checks(env_for(h), h, http=bridge, which=lambda n: "/x", py_version=PY(3, 12, 0), platform="linux")
        if c.status == "falha"
    ]


def test_home_fora_do_perfil_no_windows_e_aviso(tmp_path):
    h = tmp_path / "heycode"
    init_home(h)
    env = {**env_for(h), "USERPROFILE": "C:/Users/Ana"}
    checks = by_name(run_checks(env, h, http=Bridge(), which=lambda n: "/x", py_version=PY(3, 12, 0), platform="win32"))
    assert checks["diretorio"].status == "aviso" and "perfil" in checks["diretorio"].detail.lower()


def test_check_e_serializavel():
    c = Check("n", "ambiente", "ok", "d", "f")
    assert json.loads(json.dumps(c.__dict__))["layer"] == "ambiente"
