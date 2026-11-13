"""A1/M7: dois segredos (agente e controle), minimo de 32 caracteres."""
import importlib
import os
import sys

import pytest

BRIDGE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "bridge"))

# (metodo, rota, corpo)
CONTROL_ROUTES = [
    ("GET", "/mode", None), ("POST", "/mode", {"mode": "auto"}), ("GET", "/status", None),
    ("GET", "/pending", None), ("GET", "/result", None), ("POST", "/decide", {"approve": False}),
    ("POST", "/answer/preview", {"approval_id": 1, "text": "x"}),
    ("POST", "/answer/confirm", {"approval_id": 1, "token": "x"}),
    ("POST", "/instruction", {"text": "x"}), ("POST", "/runs", {"agent": "claude", "prompt": "x", "cwd": "."}),
    ("GET", "/runs/latest", None), ("GET", "/runs/1", None), ("POST", "/runs/1/cancel", None),
    ("POST", "/projects", {"name": "a", "agent": "claude", "description": "x"}),
    ("POST", "/confirm", None), ("POST", "/cancel", None),
    ("POST", "/dictation", {"agent": "claude", "text": "x"}), ("POST", "/dictation/confirm", None),
    ("POST", "/dictation/cancel", None),
]
AGENT_ROUTES = [
    ("POST", "/event", {"session_id": "a", "hook_event_name": "Stop"}),
    ("POST", "/approval", {"tool_name": "Read", "tool_input": {}}),
    ("POST", "/instruction/next", {"agent": "claude"}),
]


@pytest.mark.parametrize("method,path,body", CONTROL_ROUTES)
def test_segredo_de_agente_recebe_401_nas_rotas_de_controle(client, method, path, body):
    r = client.request(method, path, json=body, headers=client.agent_h)
    assert r.status_code == 401, path


@pytest.mark.parametrize("method,path,body", CONTROL_ROUTES)
def test_sem_segredo_recebe_401_nas_rotas_de_controle(client, method, path, body):
    assert client.request(method, path, json=body, headers={"x-secret": ""}).status_code == 401


@pytest.mark.parametrize("method,path,body", AGENT_ROUTES)
def test_segredo_de_controle_recebe_401_nas_rotas_de_agente(client, method, path, body):
    assert client.request(method, path, json=body, headers=client.control_h).status_code == 401, path


@pytest.mark.parametrize("method,path,body", AGENT_ROUTES)
def test_segredo_de_agente_vale_nas_rotas_de_agente(client, method, path, body):
    assert client.request(method, path, json=body, headers=client.agent_h).status_code == 200


def test_a1_poc_agente_nao_liga_o_modo_auto(client):
    """PoC do relatorio: o agente tenta POST /mode com o segredo que tem."""
    r = client.post("/mode", json={"mode": "auto"}, headers=client.agent_h)
    assert r.status_code == 401
    assert client.get("/mode").json()["mode"] == "manual"


def test_health_continua_sem_segredo(client):
    assert client.get("/health", headers={"x-secret": ""}).json() == {"ok": True}


def _import_server(tmp_path, monkeypatch, agent, control):
    monkeypatch.setenv("BRIDGE_DB", str(tmp_path / "b.db"))
    monkeypatch.setenv("NTFY_TOPIC", "")
    monkeypatch.setenv("PROJECTS_ROOT", str(tmp_path))
    if agent is None:
        monkeypatch.delenv("BRIDGE_SECRET", raising=False)
    else:
        monkeypatch.setenv("BRIDGE_SECRET", agent)
    if control is None:
        monkeypatch.delenv("BRIDGE_CONTROL_SECRET", raising=False)
    else:
        monkeypatch.setenv("BRIDGE_CONTROL_SECRET", control)
    monkeypatch.syspath_prepend(BRIDGE_DIR)
    if "server" in sys.modules:
        return importlib.reload(sys.modules["server"])
    return importlib.import_module("server")


@pytest.mark.parametrize("agent,control", [
    ("", "c" * 40), ("a" * 40, ""), ("curto", "c" * 40), ("a" * 40, "curto"),
    ("a" * 31, "c" * 40), ("a" * 40, "c" * 31), (None, "c" * 40), ("a" * 40, None),
    ("x" * 40, "x" * 40),  # iguais anulam a separacao
])
def test_m7_ponte_aborta_no_import_com_segredo_curto_ausente_ou_igual(tmp_path, monkeypatch, agent, control):
    with pytest.raises(SystemExit):
        _import_server(tmp_path, monkeypatch, agent, control)
    sys.modules.pop("server", None)


def test_m7_poc_segredo_vazio_nao_deixa_entrar_sem_credencial(tmp_path, monkeypatch):
    with pytest.raises(SystemExit):
        _import_server(tmp_path, monkeypatch, "", "")
    sys.modules.pop("server", None)


def test_32_caracteres_e_aceito(tmp_path, monkeypatch):
    server = _import_server(tmp_path, monkeypatch, "a" * 32, "c" * 32)
    try:
        assert server.SECRET == "a" * 32 and server.CONTROL_SECRET == "c" * 32
    finally:
        server.store.close()
