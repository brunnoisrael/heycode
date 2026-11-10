import sys
import time

import pytest

FAKE = [sys.executable, "-c", "import json;print(json.dumps({'result': 'ok'}))"]


@pytest.fixture(autouse=True)
def _env(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECTS_ROOT", str(tmp_path))


def _wait(pred, timeout=8.0):
    end = time.time() + timeout
    while time.time() < end:
        v = pred()
        if v:
            return v
        time.sleep(0.1)
    return None


def test_projects_e_confirm_criam_pasta_e_iniciam_run(client, tmp_path):
    client.server.supervisor._commands = {"claude": FAKE}
    r = client.post("/projects", json={"name": "Meu App", "agent": "claude", "description": "um painel"}).json()
    assert r["ok"] is True and "meu-app" in r["speech"]
    c = client.post("/confirm").json()
    assert "run_id" in c
    assert (tmp_path / "meu-app" / "AGENTS.md").exists()
    run = _wait(lambda: (x := client.get(f"/runs/{c['run_id']}").json())["status"] == "concluida" and x)
    assert run and run["project"] == "meu-app"
    assert "run_id" not in client.post("/confirm").json()


def test_projeto_existente_nao_sobrescreve(client, tmp_path):
    (tmp_path / "meu-app").mkdir()
    r = client.post("/projects", json={"name": "meu app", "agent": "claude", "description": "x"}).json()
    assert r["ok"] is False and "já existe" in r["speech"]


def test_confirm_sem_nada(client):
    r = client.post("/confirm").json()
    assert "run_id" not in r and "nada" in r["speech"].lower()


def test_confirm_com_ditado_pendente_confirma_o_ditado(client):
    client.server.supervisor._commands = {"claude": FAKE}
    assert client.post("/dictation", json={"agent": "claude", "text": "rode"}).json()["ok"]
    assert "run_id" in client.post("/confirm").json()


def test_projeto_pendente_tem_prioridade_sobre_ditado(client, tmp_path):
    client.server.supervisor._commands = {"claude": FAKE}
    client.post("/dictation", json={"agent": "claude", "text": "rode"})
    client.post("/projects", json={"name": "novo", "agent": "claude", "description": "x"})
    assert "run_id" in client.post("/confirm").json()
    assert (tmp_path / "novo").is_dir()


def test_cancel_limpa(client, tmp_path):
    client.post("/projects", json={"name": "novo", "agent": "claude", "description": "x"})
    assert "cancelado" in client.post("/cancel").json()["speech"].lower()
    assert "run_id" not in client.post("/confirm").json()
    assert not (tmp_path / "novo").exists()


def test_cancel_limpa_ditado(client):
    client.post("/dictation", json={"agent": "claude", "text": "rode"})
    client.post("/cancel")
    assert "run_id" not in client.post("/confirm").json()


def test_dictation_endpoints_antigos_seguem(client):
    client.server.supervisor._commands = {"claude": FAKE}
    client.post("/dictation", json={"agent": "claude", "text": "rode"})
    assert "run_id" in client.post("/dictation/confirm").json()
    assert "Não há" in client.post("/dictation/cancel").json()["speech"]


def test_auth(client):
    bad = {"x-secret": "errado"}
    body = {"name": "a", "agent": "claude", "description": "x"}
    assert client.post("/projects", json=body, headers=bad).status_code == 401
    assert client.post("/confirm", headers=bad).status_code == 401
    assert client.post("/cancel", headers=bad).status_code == 401
