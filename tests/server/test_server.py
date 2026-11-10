import threading
import time


def post_approval(c, cmd, tool="Bash", **extra):
    body = {"session_id": "a", "tool_name": tool, "tool_input": {"command": cmd}, "cwd": "/x/proj", **extra}
    return c.post("/approval", json=body)


def test_sem_secret_401(client):
    assert client.get("/status", headers={"x-secret": ""}).status_code == 401


def test_health(client):
    assert client.get("/health", headers={"x-secret": ""}).json() == {"ok": True}


def test_mode_roundtrip(client):
    assert client.get("/mode").json()["mode"] == "manual"
    assert client.post("/mode", json={"mode": "auto"}).status_code == 200
    assert client.get("/mode").json()["mode"] == "auto"


def test_mode_invalido_422_sem_gravar(client):
    client.post("/mode", json={"mode": "auto"})
    assert client.post("/mode", json={"mode": "banana"}).status_code == 422
    assert client.get("/mode").json()["mode"] == "auto"


def test_report_on_end_gravado_e_lido(client):
    client.post("/mode", json={"report_on_end": True})
    body = client.get("/mode").json()
    assert body["report_on_end"] is True and body["mode"] == "manual"


def test_auto_aprova_tudo(client):
    client.post("/mode", json={"mode": "auto"})
    assert post_approval(client, "rm -rf x").json() == {"decision": "allow"}


def test_manual_destrutivo_pede_teclado(client):
    assert post_approval(client, "rm -rf x").json() == {"decision": "ask"}


def test_decisoes_read_allow(client):
    client.post("/mode", json={"mode": "decisoes"})
    r = client.post("/approval", json={"tool_name": "Read", "tool_input": {"file_path": "a"}})
    assert r.json() == {"decision": "allow"}


def test_event_e_status(client):
    client.post("/event", json={"session_id": "s1", "cwd": "/a/meuproj", "hook_event_name": "UserPromptSubmit",
                                "prompt": "faz algo"})
    speech = client.get("/status").json()["speech"]
    assert "meuproj" in speech and "trabalhando" in speech


def test_event_agent_padrao_e_result(client, tmp_path):
    client.post("/event", json={"session_id": "s1", "cwd": "/a/p", "hook_event_name": "Stop",
                                "transcript_path": str(tmp_path / "nao-existe")})
    assert client.server.store.newest_session()["agent"] == "claude"
    assert client.get("/result").json()["speech"] == "Ainda não há um resumo disponível."


def test_manual_sem_decisao_expira(client):
    assert post_approval(client, "ls").json() == {"decision": "ask"}
    assert client.server.store.get_approval(1)["decision"] == "expired"
    assert client.server.store.pending_approvals() == []


def test_sem_pin_ask(client, monkeypatch):
    monkeypatch.setattr(client.server, "PIN", "")
    assert post_approval(client, "ls").json() == {"decision": "ask"}


def test_decide_com_pin_libera(client, monkeypatch):
    monkeypatch.setattr(client.server, "APPROVAL_WAIT", 10)
    out = {}
    t = threading.Thread(target=lambda: out.update(post_approval(client, "ls").json()))
    t.start()
    for _ in range(50):
        if client.get("/pending").json()["actionable"]:
            break
        time.sleep(0.1)
    assert "ls" in client.get("/pending").json()["speech"]
    client.post("/event", json={"session_id": "a", "cwd": "/x/proj", "hook_event_name": "PreToolUse"})
    assert "esperando" in client.get("/status").json()["speech"]
    assert client.post("/decide", json={"approve": True, "pin": "0000"}).json()["speech"] == "PIN incorreto."
    assert client.post("/decide", json={"approve": True, "pin": "1234"}).json()["speech"].startswith("Aprovado")
    t.join(5)
    assert out == {"decision": "allow"}


def test_decide_negar(client, monkeypatch):
    monkeypatch.setattr(client.server, "APPROVAL_WAIT", 10)
    out = {}
    t = threading.Thread(target=lambda: out.update(post_approval(client, "ls").json()))
    t.start()
    for _ in range(50):
        if client.get("/pending").json()["actionable"]:
            break
        time.sleep(0.1)
    assert client.post("/decide", json={"approve": False}).json()["speech"].startswith("Negado")
    t.join(5)
    assert out == {"decision": "deny"}


def test_decide_sem_pendente(client):
    assert client.post("/decide", json={"approve": True, "pin": "1234"}).json()["speech"] == "Não há nada aguardando decisão."


def test_startup_expira_pendentes(tmp_path, client):
    s = client.server.store
    aid = s.add_approval("claude", "p", "Bash", "ls", "x")
    with __import__("fastapi.testclient", fromlist=["TestClient"]).TestClient(client.server.app):
        pass
    assert s.get_approval(aid)["decision"] == "expired"
