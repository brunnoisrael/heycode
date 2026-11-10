"""Onda 2b: relatorios, resumo e trava de PIN sobrevivem a reinicio (ADR 0015)."""
import importlib
import json
import sys
import time

from fastapi.testclient import TestClient

from conftest import AGENT_SECRET, CONTROL_SECRET


def restart(client):
    """Fecha o Store, reabre o mesmo arquivo e recarrega o server."""
    client.server.store.close()
    server = importlib.reload(sys.modules["server"])
    c = TestClient(server.app, headers={"x-secret": CONTROL_SECRET})
    c.server = server
    return c


def test_fim_de_ciclo_sobrevive_ao_reinicio_e_nao_repete(client):
    st = client.server.store
    st.set_policy(report_on_end=True)
    rid = st.create_run("claude", "proj", "x", "/x")
    st.update_run(rid, status="concluida", summary="tudo certo")
    client.server._on_run_finished(st.get_run(rid))
    c2 = restart(client)
    try:
        assert "terminou no projeto proj" in c2.get("/pending").json()["speech"]
        assert "tudo certo" in c2.get("/result").json()["speech"]
        assert "Nada pendente" in c2.get("/pending").json()["speech"]
        c3 = restart(c2)
        assert "Nada pendente" in c3.get("/pending").json()["speech"]
        c3.server.store.close()
    except Exception:
        c2.server.store.close()
        raise


def test_run_interrompida_no_startup_nao_gera_aviso(client):
    st = client.server.store
    st.set_policy(report_on_end=True)
    rid = st.create_run("claude", "proj", "x", "/x")  # fica 'rodando'
    c2 = restart(client)
    try:
        assert c2.server.store.get_run(rid)["status"] == "interrompida"
        assert "Nada pendente" in c2.get("/pending").json()["speech"]
    finally:
        c2.server.store.close()


def test_resumo_da_sessao_sobrevive_ao_reinicio_e_a_eventos_seguintes(client, tmp_path):
    tr = tmp_path / "t.jsonl"
    tr.write_text(json.dumps({"type": "assistant", "message": {"content": [
        {"type": "text", "text": "fiz a migracao"}]}}) + "\n", encoding="utf-8")
    client.post("/event", json={"session_id": "s1", "cwd": "/a/p", "hook_event_name": "Stop",
                                "transcript_path": str(tr)}, headers=client.agent_h)
    client.post("/event", json={"session_id": "s1", "cwd": "/a/p", "hook_event_name": "PreToolUse",
                                "tool_name": "Read", "tool_input": {}}, headers=client.agent_h)
    c2 = restart(client)
    try:
        assert "fiz a migracao" in c2.get("/result").json()["speech"]
        c2.post("/event", json={"session_id": "s1", "cwd": "/a/p", "hook_event_name": "UserPromptSubmit",
                                "prompt": "outra"}, headers={"x-secret": AGENT_SECRET})
        assert "fiz a migracao" in c2.get("/result").json()["speech"]
    finally:
        c2.server.store.close()


def test_trava_de_pin_sobrevive_ao_reinicio(client):
    client.server.store.add_approval("claude", "p", "Bash", "npm x", "s")
    for _ in range(3):
        r = client.post("/decide", json={"approve": True, "pin": "0000"}).json()
    assert "bloqueada" in r["speech"]
    c2 = restart(client)
    try:
        c2.server.store.add_approval("claude", "p", "Bash", "npm y", "s")
        r = c2.post("/decide", json={"approve": True, "pin": "1234"}).json()
        assert "bloqueada" in r["speech"]
        assert c2.server.store.pending_approvals()
    finally:
        c2.server.store.close()


def test_contagem_de_erros_do_pin_sobrevive_ao_reinicio(client):
    client.server.store.add_approval("claude", "p", "Bash", "npm x", "s")
    client.post("/decide", json={"approve": True, "pin": "0000"})
    client.post("/decide", json={"approve": True, "pin": "0000"})
    c2 = restart(client)
    try:
        c2.server.store.add_approval("claude", "p", "Bash", "npm y", "s")
        assert "três vezes" in c2.post("/decide", json={"approve": True, "pin": "0000"}).json()["speech"]
    finally:
        c2.server.store.close()


def test_b1_cancela_a_run_mais_recente_em_andamento(client):
    class Fake:
        def __init__(self):
            self.cancelled = []
        def cancel(self, rid):
            self.cancelled.append(rid)
            return True
    st = client.server.store
    old = st.create_run("claude", "p", "x", "/x")
    new = st.create_run("codex", "p", "x", "/x")
    fake = Fake()
    client.server.supervisor.cancel = fake.cancel
    r = client.post("/runs/latest/cancel")
    assert r.status_code == 200 and r.json() == {"speech": "Cancelei o agente codex."}
    assert fake.cancelled == [new] and old not in fake.cancelled


def test_b1_sem_run_rodando(client):
    assert client.post("/runs/latest/cancel").json() == {"speech": "Nenhum agente rodando."}


def test_b1_exige_segredo_de_controle(client):
    assert client.post("/runs/latest/cancel", headers=client.agent_h).status_code == 401
