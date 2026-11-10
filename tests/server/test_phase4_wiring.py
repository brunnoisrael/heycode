import sys
import time

import pytest

FAKE_RESULT = "tarefa feita"
FAKE = [sys.executable, "-c", f"import json;print(json.dumps({{'result': '{FAKE_RESULT}'}}))"]


@pytest.fixture(autouse=True)
def _env(tmp_path, monkeypatch):
    """Roda antes do fixture `client`: raiz de projetos temporaria."""
    monkeypatch.setenv("PROJECTS_ROOT", str(tmp_path))


def _wait(predicate, timeout=8.0):
    end = time.time() + timeout
    while time.time() < end:
        value = predicate()
        if value:
            return value
        time.sleep(0.1)
    return None


def _run_via_voice(client, text="rode os testes"):
    client.server.supervisor._commands = {"claude": FAKE}
    assert client.post("/dictation", json={"agent": "claude", "text": text}).json()["ok"] is True
    confirm = client.post("/dictation/confirm").json()
    assert "run_id" in confirm
    return confirm["run_id"]


def test_ditado_confirmado_inicia_run_e_conclui(client):
    run_id = _run_via_voice(client)
    run = _wait(lambda: (r := client.get(f"/runs/{run_id}").json())["status"] == "concluida" and r)
    assert run and run["summary"] == FAKE_RESULT
    assert client.get("/runs/latest").json()["id"] == run_id


def test_rotas_novas_exigem_auth(client):
    anon = {"x-secret": "errado"}
    assert client.post("/dictation", json={"agent": "claude", "text": "x"}, headers=anon).status_code == 401
    assert client.post("/runs", json={"agent": "claude", "prompt": "x"}, headers=anon).status_code == 401
    assert client.get("/runs/latest", headers=anon).status_code == 401


def test_agente_desconhecido_em_runs_da_400(client):
    assert client.post("/runs", json={"agent": "naoexiste", "prompt": "x", "cwd": client.server.PROJECTS_ROOT}).status_code == 400


def test_confirmar_sem_ditado_nao_inicia_nada(client):
    res = client.post("/dictation/confirm").json()
    assert "run_id" not in res


def test_report_on_end_avisa_e_o_resultado_le_o_resumo(client):
    client.post("/mode", json={"report_on_end": True})
    run_id = _run_via_voice(client)
    pending = _wait(lambda: "terminou" in (p := client.get("/pending").json())["speech"] and p)
    assert pending and "ouvir" in pending["speech"]
    result = client.get("/result").json()["speech"]
    assert FAKE_RESULT in result
    assert "Nada pendente" in client.get("/pending").json()["speech"]


def test_sem_report_on_end_nao_avisa(client):
    run_id = _run_via_voice(client)
    _wait(lambda: client.get(f"/runs/{run_id}").json()["status"] == "concluida")
    assert "terminou" not in client.get("/pending").json()["speech"]


def test_reinicio_marca_runs_em_andamento_como_interrompidas(tmp_path, monkeypatch):
    import importlib

    from fastapi.testclient import TestClient

    monkeypatch.setenv("BRIDGE_SECRET", "a" * 40)
    monkeypatch.setenv("BRIDGE_CONTROL_SECRET", "c" * 40)
    monkeypatch.setenv("BRIDGE_DB", str(tmp_path / "restart.db"))
    monkeypatch.setenv("BRIDGE_PIN", "1234")
    monkeypatch.setenv("NTFY_TOPIC", "")
    import os
    monkeypatch.syspath_prepend(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "bridge")))
    from store.db import Store

    seed = Store(str(tmp_path / "restart.db"))
    run_id = seed.create_run("codex", "proj", "algo", str(tmp_path))
    seed.update_run(run_id, status="rodando")
    seed.close()

    server = importlib.reload(sys.modules["server"]) if "server" in sys.modules else importlib.import_module("server")
    with TestClient(server.app, headers={"x-secret": "c" * 40}) as c:
        assert c.get(f"/runs/{run_id}").json()["status"] == "interrompida"
    server.store.close()
