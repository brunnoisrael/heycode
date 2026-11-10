"""ADR 0019: execucao pedida por voz sempre volta por voz ao terminar, com o que o agente respondeu."""
import sys
import time

import pytest

SK = "sk-ABCDEFGHIJKLMNOPQRSTUV"
FAKE_OK = [sys.executable, "-c", "import json;print(json.dumps({'result': 'tarefa feita'}))"]
FAKE_SEGREDO = [sys.executable, "-c", f"import json;print(json.dumps({{'result': 'a chave e {SK}'}}))"]


@pytest.fixture(autouse=True)
def _env(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECTS_ROOT", str(tmp_path))


def _wait(predicate, timeout=8.0):
    end = time.time() + timeout
    while time.time() < end:
        value = predicate()
        if value:
            return value
        time.sleep(0.1)
    return None


def _done(client, run_id):
    assert _wait(lambda: client.get(f"/runs/{run_id}").json()["status"] != "rodando")
    time.sleep(0.3)  # deixa o callback de fim rodar


def _run_via_voice(client, fake=FAKE_OK):
    client.server.supervisor._commands = {"claude": fake}
    assert client.post("/dictation", json={"agent": "claude", "text": "rode os testes"}).json()["ok"] is True
    run_id = client.post("/dictation/confirm").json()["run_id"]
    _done(client, run_id)
    return run_id


def _run_direto(client, fake=FAKE_OK):
    client.server.supervisor._commands = {"claude": fake}
    run_id = client.post("/runs", json={"agent": "claude", "prompt": "x", "cwd": client.server.PROJECTS_ROOT}).json()["run_id"]
    _done(client, run_id)
    return run_id


def test_sucesso_pedido_por_voz_entra_na_fila_com_report_on_end_desligado(client):
    assert client.get("/mode").json()["report_on_end"] is False
    _run_via_voice(client)
    p = client.get("/pending").json()
    assert p["speech"].startswith("O agente claude terminou no projeto ") and "ouvir" in p["speech"]
    r = client.get("/result").json()["speech"]
    assert r.startswith("O agente claude terminou no projeto ") and r.endswith("Resultado: tarefa feita")
    assert "Nada pendente" in client.get("/pending").json()["speech"]  # falado uma vez so


def test_status_fala_o_resultado_antes_da_sessao_e_uma_vez_so(client):
    client.post("/event", json={"session_id": "s1", "cwd": "/a/outro", "hook_event_name": "UserPromptSubmit",
                                "prompt": "algo"}, headers=client.agent_h)
    _run_via_voice(client)
    speech = client.get("/status").json()["speech"]
    assert speech.startswith("O agente claude terminou no projeto ")
    assert "Resultado: tarefa feita." in speech and speech.index("tarefa feita") < speech.index("No projeto outro")
    assert "terminou" not in client.get("/status").json()["speech"]
    assert client.get("/result").json()["speech"].startswith("Resumo do projeto") is False


def test_status_fala_o_resultado_mesmo_sem_sessao(client):
    _run_via_voice(client)
    assert "Resultado: tarefa feita" in client.get("/status").json()["speech"]
    assert "Nenhuma sessão" in client.get("/status").json()["speech"]


def test_run_direta_continua_respeitando_report_on_end(client):
    _run_direto(client)
    assert "Nada pendente" in client.get("/pending").json()["speech"]
    assert "Nenhuma sessão" in client.get("/status").json()["speech"]
    client.post("/mode", json={"report_on_end": True})
    _run_direto(client)
    assert "terminou" in client.get("/pending").json()["speech"]


def test_cancelada_por_voz_nao_entra_na_fila(client):
    st = client.server.store
    rid = st.create_run("claude", "proj", "x", "/x")
    client.server._voice_runs.add(rid)
    st.update_run(rid, status="cancelada", summary="parou")
    client.server._on_run_finished(st.get_run(rid))
    assert "Nada pendente" in client.get("/pending").json()["speech"]


def test_resultado_falado_sai_mascarado(client):
    _run_via_voice(client, FAKE_SEGREDO)
    speech = client.get("/status").json()["speech"]
    assert "terminou" in speech and "[segredo]" in speech and SK not in speech


def test_projeto_criado_por_voz_tambem_volta(client):
    """`_start_run` e o caminho unico da voz (ditado e projeto novo): toda run dele entra na fila."""
    client.server.supervisor._commands = {"claude": FAKE_OK}
    run_id = client.server._start_run("claude", "x", None)
    _done(client, run_id)
    assert "terminou" in client.get("/pending").json()["speech"]
