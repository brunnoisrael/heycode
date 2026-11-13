"""Ponta a ponta na ponte: "avise o agente aberto" -> confirma -> fila -> hook Stop (ADR 0018)."""
import json
import os
import socket
import subprocess
import sys
import threading
import time

import pytest

HOOK = ["-m", "heycode.hook"]
PREFIX = "Instrução do dono, ditada pela Alexa e confirmada por voz: "


def _session(client, event="UserPromptSubmit", cwd="/x/painel", agent=None):
    body = {"hook_event_name": event, "session_id": "s1", "cwd": cwd, "prompt": "oi"}
    if agent:
        body["agent"] = agent
    assert client.post("/event", json=body, headers=client.agent_h).status_code == 200


def _next(client, agent="claude", project="painel"):
    return client.post("/instruction/next", json={"agent": agent, "project": project},
                       headers=client.agent_h).json()["instruction"]


def test_ditado_para_o_agente_aberto_confirma_e_sai_uma_unica_vez(client):
    _session(client)
    r = client.post("/dictation", json={"target": "aberto", "text": "rode os testes"}).json()
    assert r == {"speech": "Entendi, para o agente aberto no projeto painel: rode os testes. Confirma?", "ok": True}
    assert _next(client) is None  # nada vai para a fila antes do "confirma"
    r = client.post("/confirm").json()
    assert r["speech"] == "Instrução na fila do agente aberto no projeto painel. Ele recebe ao terminar o turno atual."
    assert isinstance(r["instruction_id"], int) and "run_id" not in r
    assert client.server.store.latest_run() is None  # nenhuma run headless foi iniciada
    assert _next(client, project="outro") is None  # outro projeto nao recebe
    assert _next(client, agent="codex") is None    # outro agente nao recebe
    assert _next(client) == "rode os testes"
    assert _next(client) is None                    # entrega unica
    assert client.post("/confirm").json()["speech"] == "Não há nada para confirmar."


def test_lambda_so_tem_o_segredo_de_controle(client):
    """A Lambda propoe e confirma com o segredo de controle; a fila so sai com o de agente."""
    _session(client)
    body = {"target": "aberto", "text": "x"}
    assert client.post("/dictation", json=body, headers=client.agent_h).status_code == 401
    assert client.post("/confirm", headers=client.agent_h).status_code == 401
    assert client.post("/dictation", json=body, headers=client.control_h).status_code == 200
    assert client.post("/confirm", headers=client.control_h).status_code == 200
    nxt = {"agent": "claude", "project": "painel"}
    assert client.post("/instruction/next", json=nxt, headers=client.control_h).status_code == 401
    assert client.post("/instruction/next", json=nxt, headers=client.agent_h).json() == {"instruction": "x"}


def test_sem_sessao_aberta_recusa_e_nada_entra_na_fila(client):
    r = client.post("/dictation", json={"target": "aberto", "text": "x"}).json()
    assert r == {"speech": "Não achei nenhum agente aberto com atividade recente. Nada foi enviado.", "ok": False}
    assert client.post("/confirm").json()["speech"] == "Não há nada para confirmar."


def test_sessao_antiga_nao_conta_como_aberta(client, monkeypatch):
    _session(client)
    monkeypatch.setattr(client.server, "OPEN_SESSION_WINDOW", -1)
    assert client.post("/dictation", json={"target": "aberto", "text": "x"}).json()["ok"] is False


def test_sessao_parada_enfileira_e_avisa(client):
    _session(client, event="Stop")
    client.post("/dictation", json={"target": "aberto", "text": "x"})
    assert client.post("/confirm").json()["speech"].endswith("Ele está parado e só recebe ao fim do próximo turno.")
    assert _next(client) == "x"


@pytest.mark.skipif(sys.platform != "win32", reason="usa caminho do Windows (barra invertida)")
def test_destino_e_a_sessao_mais_recente(client):
    _session(client, cwd="/x/antigo")
    client.post("/event", json={"hook_event_name": "PreToolUse", "session_id": "s2", "cwd": "C:\\p\\novo",
                                "agent": "codex", "tool_name": "Read"}, headers=client.agent_h)
    r = client.post("/dictation", json={"target": "aberto", "text": "x"}).json()
    assert "no projeto novo" in r["speech"]
    client.post("/confirm")
    assert _next(client, project="antigo") is None
    assert _next(client, agent="codex", project="novo") == "x"


def test_instrucao_velha_expira_sem_entrega(client, monkeypatch):
    _session(client)
    client.post("/dictation", json={"target": "aberto", "text": "x"})
    client.post("/confirm")
    monkeypatch.setattr(client.server, "INSTRUCTION_TTL", -1)
    assert _next(client) is None
    monkeypatch.setattr(client.server, "INSTRUCTION_TTL", 1800)
    assert _next(client) is None  # expirada nao volta


def test_cancelar_descarta_o_ditado_para_o_aberto(client):
    _session(client)
    client.post("/dictation", json={"target": "aberto", "text": "x"})
    assert client.post("/cancel").json()["speech"] == "Ditado cancelado."
    assert client.post("/confirm").json()["speech"] == "Não há nada para confirmar."
    assert _next(client) is None


def test_destino_invalido_422_e_ditado_antigo_intacto(client):
    assert client.post("/dictation", json={"target": "todos", "text": "x"}).status_code == 422
    r = client.post("/dictation", json={"agent": "claude", "text": "faz x"}).json()
    assert r == {"speech": "Entendi, para o claude: faz x. Confirma?", "ok": True}
    assert client.post("/dictation", json={"text": "faz x"}).json()["ok"] is False  # "run" exige agente
    client.post("/cancel")


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _hook(payload, url, secret):
    env = dict(os.environ, BRIDGE_URL=url, BRIDGE_SECRET=secret)
    return subprocess.run([sys.executable, *HOOK], input=json.dumps(payload).encode("utf-8"),
                          capture_output=True, env=env, timeout=30)


def test_hook_stop_real_recebe_o_bloco_com_a_instrucao(client, tmp_path):
    """hook.py de verdade contra a ponte num uvicorn: sessao aberta -> ditado -> confirma -> Stop bloqueia."""
    import uvicorn

    port = _free_port()
    srv = uvicorn.Server(uvicorn.Config(client.server.app, host="127.0.0.1", port=port, log_level="error"))
    th = threading.Thread(target=srv.run, daemon=True)
    th.start()
    for _ in range(100):
        if srv.started:
            break
        time.sleep(0.05)
    assert srv.started
    url, secret = f"http://127.0.0.1:{port}", client.agent_h["x-secret"]
    cwd = str(tmp_path / "painel")
    try:
        r = _hook({"hook_event_name": "UserPromptSubmit", "session_id": "s1", "cwd": cwd, "prompt": "oi"}, url, secret)
        assert r.returncode == 0 and r.stdout == b""
        d = client.post("/dictation", json={"target": "aberto", "text": "rode os testes de integração"}).json()
        assert d["ok"] is True and "no projeto painel" in d["speech"]
        assert client.post("/confirm").json()["speech"].startswith("Instrução na fila do agente aberto")
        stop = {"hook_event_name": "Stop", "session_id": "s1", "cwd": cwd}
        r = _hook(stop, url, secret)
        assert r.returncode == 0
        assert json.loads(r.stdout) == {"decision": "block", "reason": PREFIX + "rode os testes de integração"}
        r = _hook(stop, url, secret)  # o Stop seguinte nao segura mais o turno
        assert r.returncode == 0 and r.stdout == b""
        r = _hook(stop, url, client.control_h["x-secret"])  # segredo errado: falha aberta, sem saida
        assert r.returncode == 0 and r.stdout == b""
    finally:
        srv.should_exit = True
        th.join(5)
