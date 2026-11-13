"""ADR 0017: run que falha e sempre avisada por voz, com motivo legivel e mascarado."""
import json
import sys
import time

import pytest

SK = "sk-ABCDEFGHIJKLMNOPQRSTUV"
MSG = "API Error: 400 Claude Code 2.1.207 does not support this model; version 2.1.290 or newer is required."
_PAYLOAD = {"type": "result", "subtype": "success", "is_error": True, "result": MSG,
            "usage": {"input_tokens": 0}, "terminal_reason": "api_error", "uuid": "f942b57e"}
FAKE_FALHA = [sys.executable, "-c", f"import sys;print({json.dumps(json.dumps(_PAYLOAD))});sys.exit(1)"]
FAKE_OK = [sys.executable, "-c", "import json;print(json.dumps({'result': 'tarefa feita'}))"]


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


def _run_via_voice(client, fake):
    client.server.supervisor._commands = {"claude": fake}
    assert client.post("/dictation", json={"agent": "claude", "text": "rode os testes"}).json()["ok"] is True
    run_id = client.post("/dictation/confirm").json()["run_id"]
    assert _wait(lambda: client.get(f"/runs/{run_id}").json()["status"] != "rodando")
    return run_id


def _falha(client, summary, agent="claude", project="proj"):
    """Grava uma run que falhou e dispara o callback de fim, como o supervisor faz."""
    st = client.server.store
    rid = st.create_run(agent, project, "x", "/x")
    st.update_run(rid, status="falhou", summary=summary, exit_code=1)
    client.server._on_run_finished(st.get_run(rid))
    return rid


def test_falha_aparece_em_pending_com_report_on_end_desligado(client):
    assert client.get("/mode").json()["report_on_end"] is False
    run_id = _run_via_voice(client, FAKE_FALHA)
    assert client.get(f"/runs/{run_id}").json()["summary"] == MSG
    p = _wait(lambda: "falhou" in (p := client.get("/pending").json())["speech"] and p)
    assert p and p["actionable"] is False and p["approval_id"] is None
    assert p["speech"].startswith("O agente claude falhou no projeto ") and MSG in p["speech"]
    assert "terminal_reason" not in p["speech"] and "{" not in p["speech"]
    assert "Nada pendente" in client.get("/pending").json()["speech"]  # avisado uma vez so


def test_falha_aparece_em_result_com_report_on_end_desligado(client):
    _falha(client, MSG)
    speech = client.get("/result").json()["speech"]
    assert speech == f"O agente claude falhou no projeto proj: {MSG}"
    assert "falhou" not in client.get("/result").json()["speech"]


def test_falha_entra_no_status_antes_da_sessao(client):
    client.post("/event", json={"session_id": "s1", "cwd": "/a/outro", "hook_event_name": "UserPromptSubmit",
                                "prompt": "algo"}, headers=client.agent_h)
    _falha(client, MSG, agent="codex")
    speech = client.get("/status").json()["speech"]
    assert speech.startswith("O agente codex falhou no projeto proj: ") and "No projeto outro" in speech
    assert "falhou" not in client.get("/status").json()["speech"]


def test_falha_entra_no_status_mesmo_sem_sessao(client):
    _falha(client, MSG)
    assert "falhou no projeto proj" in client.get("/status").json()["speech"]
    assert "Nenhuma sessão" in client.get("/status").json()["speech"]


def test_sucesso_de_run_direta_nao_aparece_com_report_on_end_desligado(client):
    """Sucesso pedido por voz volta sempre (ADR 0019); o de POST /runs continua dependendo de report_on_end."""
    client.server.supervisor._commands = {"claude": FAKE_OK}
    run_id = client.post("/runs", json={"agent": "claude", "prompt": "x",
                                        "cwd": client.server.PROJECTS_ROOT}).json()["run_id"]
    assert _wait(lambda: client.get(f"/runs/{run_id}").json()["status"] != "rodando")
    time.sleep(0.3)  # deixa o callback de fim rodar
    assert "Nada pendente" in client.get("/pending").json()["speech"]
    assert client.get("/result").json()["speech"] == "Ainda não há um resumo disponível."
    assert "Nenhuma sessão" in client.get("/status").json()["speech"]


def test_cancelada_nao_aparece_com_report_on_end_desligado(client):
    st = client.server.store
    rid = st.create_run("claude", "proj", "x", "/x")
    st.update_run(rid, status="cancelada", summary="parou")
    client.server._on_run_finished(st.get_run(rid))
    assert "Nada pendente" in client.get("/pending").json()["speech"]


def test_segredo_no_erro_sai_mascarado(client):
    _falha(client, f"API Error: 401 chave {SK} recusada, token=abc123segredo")
    speech = client.get("/pending").json()["speech"]
    assert "falhou" in speech and "[segredo]" in speech
    assert SK not in speech and "abc123segredo" not in speech


def test_resumo_em_json_cru_nao_e_lido(client):
    _falha(client, '"permission_denials":[],"terminal_reason":"api_error","uuid":"a436e0c3"}')
    speech = client.get("/pending").json()["speech"]
    assert "falhou no projeto proj" in speech and "Não consegui identificar o motivo" in speech
    assert "terminal_reason" not in speech and "uuid" not in speech


def test_motivo_longo_e_limitado(client):
    _falha(client, "erro " + "palavra " * 200)
    assert len(client.get("/pending").json()["speech"]) < 260


def test_falha_com_cauda_de_saida_fala_so_a_ultima_linha(client):
    _falha(client, "Traceback (most recent call last):\n  File x.py\nValueError: deu ruim", agent="aider")
    speech = client.get("/result").json()["speech"]
    assert speech == "O agente aider falhou no projeto proj: ValueError: deu ruim."


def test_aprovacao_pendente_vem_antes_e_nao_consome_a_falha(client):
    _falha(client, MSG)
    aid = client.server.store.add_approval("claude", "p", "Bash", "npm test", "s")
    assert client.get("/pending").json()["approval_id"] == aid
    client.server.store.resolve_approval(aid, "deny")
    assert "falhou" in client.get("/pending").json()["speech"]


def test_falha_sobrevive_ao_reinicio(client):
    import importlib

    from fastapi.testclient import TestClient

    from conftest import CONTROL_SECRET

    _falha(client, MSG)
    client.server.store.close()
    server = importlib.reload(sys.modules["heycode.app"])
    c2 = TestClient(server.app, headers={"x-secret": CONTROL_SECRET})
    try:
        assert MSG in c2.get("/pending").json()["speech"]
    finally:
        server.store.close()


def test_push_de_falha_leva_o_motivo_mascarado(client, monkeypatch):
    sent = []
    monkeypatch.setattr(client.server, "push", lambda title, body: sent.append((title, body)))
    _falha(client, MSG, agent="codex")
    _falha(client, '{"type":"turn.failed"}')
    st = client.server.store
    rid = st.create_run("claude", "proj", "x", "/x")
    st.update_run(rid, status="concluida", summary="tudo certo")
    client.server._on_run_finished(st.get_run(rid))
    assert sent == [("codex falhou", MSG), ("claude falhou", "Falhou sem motivo identificado"),
                    ("claude terminou", "tudo certo")]
