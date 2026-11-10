"""A3 (fala mascarada), A4 (decisao amarrada ao id), M3 (fala do modo), M1/M6 (caminhos validados)."""
import json
import os

import pytest

SK = "sk-ABCDEFGHIJKLMNOPQRSTUV"


@pytest.fixture(autouse=True)
def _root(tmp_path, monkeypatch):
    root = tmp_path / "projetos"
    root.mkdir()
    monkeypatch.setenv("PROJECTS_ROOT", str(root))
    return root


@pytest.fixture
def root(_root):
    return _root


# ---------- A3 ----------

def test_a3_pending_mascara_o_comando(client):
    client.server.store.add_approval("claude", "p", "Bash", f"curl -H 'Authorization: Bearer {SK}' https://x", "s")
    speech = client.get("/pending").json()["speech"]
    assert SK not in speech and "curl" in speech


def test_a3_status_mascara_o_prompt(client):
    client.post("/event", json={"session_id": "s1", "cwd": "/a/p", "hook_event_name": "UserPromptSubmit",
                                "prompt": "use a senha=hunter2 no deploy"}, headers=client.agent_h)
    assert "hunter2" not in client.get("/status").json()["speech"]


def test_a3_pending_mascara_a_notificacao_no_teclado(client):
    client.post("/event", json={"session_id": "s1", "cwd": "/a/p", "hook_event_name": "Notification",
                                "message": "digite TOKEN=ghp_abcdefghijklmnopqrstuvwxyz0123456789"},
                headers=client.agent_h)
    assert "ghp_" not in client.get("/pending").json()["speech"]


def test_a3_describe_tool_pula_variaveis_iniciais(client):
    d = client.server.describe_tool
    out = d({"tool_name": "Bash", "tool_input": {"command": "OPENAI_API_KEY=sk-proj-AAAAAAAAAAAAAAAA python run.py"}})
    assert out == "rodando o comando python"
    assert d({"tool_name": "Bash", "tool_input": {"command": "A=1 B=2 npm test"}}) == "rodando o comando npm"
    assert d({"tool_name": "Bash", "tool_input": {"command": "KEY=v"}}) == "rodando um comando"


def test_a3_poc_status_nao_fala_a_chave_do_comando(client):
    client.post("/event", json={"session_id": "s1", "cwd": "/a/p", "hook_event_name": "PreToolUse",
                                "tool_name": "Bash",
                                "tool_input": {"command": "OPENAI_API_KEY=sk-proj-AAAAAAAAAAAAAAAA python run.py"}},
                headers=client.agent_h)
    assert "sk-proj" not in client.get("/status").json()["speech"]


def test_a3_result_mascara_o_resumo_do_transcript(client, tmp_path):
    tr = tmp_path / "t.jsonl"
    tr.write_text(json.dumps({"type": "assistant", "message": {"content": [
        {"type": "text", "text": f"usei GITHUB_TOKEN=ghp_abcdefghijklmnopqrstuvwxyz0123456789 e {SK}"}]}}) + "\n",
        encoding="utf-8")
    client.post("/event", json={"session_id": "s1", "cwd": "/a/p", "hook_event_name": "Stop",
                                "transcript_path": str(tr)}, headers=client.agent_h)
    speech = client.get("/result").json()["speech"]
    assert "ghp_" not in speech and SK not in speech and "Resumo do projeto" in speech


def test_a3_result_mascara_o_resumo_da_run(client):
    store = client.server.store
    rid = store.create_run("claude", "p", "x", "/x")
    store.update_run(rid, status="concluida", summary=f"chave {SK}")
    client.server._unreported.append(rid)
    assert SK not in client.get("/result").json()["speech"]


def test_a3_say_e_o_helper_unico(client):
    assert SK not in client.server.say(f"a {SK} b")


# ---------- A4 ----------

def _two_pending(client):
    st = client.server.store
    a = st.add_approval("claude", "p1", "Bash", "npm test", "s")
    b = st.add_approval("codex", "p2", "Bash", "rm tudo", "s")
    return a, b


def test_a4_pending_devolve_approval_id(client):
    assert client.get("/pending").json().get("approval_id", "ausente") is None
    a, _ = _two_pending(client)
    assert client.get("/pending").json()["approval_id"] == a


def test_a4_poc_expirou_o_lido_nao_aprova_o_seguinte(client):
    a, b = _two_pending(client)
    st = client.server.store
    lido = client.get("/pending").json()["approval_id"]
    st.resolve_approval(a, "expired")  # prazo de A acabou enquanto o dono falava o PIN
    out = client.post("/decide", json={"approve": True, "pin": "1234", "approval_id": lido}).json()
    assert out["speech"] == "Esse pedido já expirou."
    assert st.get_approval(b)["decision"] is None


def test_a4_id_que_nao_e_o_mais_antigo_nao_aprova_nada(client):
    a, b = _two_pending(client)
    out = client.post("/decide", json={"approve": True, "pin": "1234", "approval_id": b}).json()
    assert out["speech"] == "Esse pedido mudou. Pergunte de novo."
    assert client.server.store.get_approval(a)["decision"] is None
    assert client.server.store.get_approval(b)["decision"] is None


def test_a4_id_correto_aprova_e_negar_tambem(client):
    a, b = _two_pending(client)
    assert client.post("/decide", json={"approve": True, "pin": "1234", "approval_id": a}).json()["speech"].startswith("Aprovado")
    assert client.server.store.get_approval(a)["decision"] == "allow"
    assert client.post("/decide", json={"approve": False, "approval_id": b}).json()["speech"].startswith("Negado")
    assert client.server.store.get_approval(b)["decision"] == "deny"


def test_a4_id_errado_nao_conta_falha_de_pin(client):
    a, b = _two_pending(client)
    for _ in range(4):
        client.post("/decide", json={"approve": True, "pin": "0000", "approval_id": b})
    assert client.post("/decide", json={"approve": True, "pin": "1234", "approval_id": a}).json()["speech"].startswith("Aprovado")


def test_a4_sem_id_mantem_o_comportamento(client):
    a, _ = _two_pending(client)
    assert client.post("/decide", json={"approve": True, "pin": "1234"}).json()["speech"].startswith("Aprovado")
    assert client.server.store.get_approval(a)["decision"] == "allow"


# ---------- M3 ----------

def test_m3_mode_post_e_get_falam_pt_br(client):
    r = client.post("/mode", json={"mode": "auto"}).json()
    assert set(r) == {"mode", "report_on_end", "speech"}
    assert r["speech"] == "Modo automático ativado para todos os agentes."
    g = client.get("/mode").json()
    assert set(g) == {"mode", "report_on_end", "speech"} and g["mode"] == "auto" and g["speech"]


@pytest.mark.parametrize("body,trecho", [
    ({"mode": "manual"}, "Modo manual ativado"),
    ({"mode": "decisoes"}, "Modo decisões ativado"),
    ({"report_on_end": True}, "fim de ciclo ligado"),
    ({"report_on_end": False}, "fim de ciclo desligado"),
])
def test_m3_falas(client, body, trecho):
    assert trecho in client.post("/mode", json=body).json()["speech"]


def test_m3_fala_com_projeto(client):
    assert "meuproj" in client.post("/mode", json={"mode": "manual", "project": "meuproj"}).json()["speech"]


# ---------- M1 / M6 ----------

@pytest.fixture
def started(client, monkeypatch):
    calls = []
    monkeypatch.setattr(client.server.supervisor, "start",
                        lambda agent, text, cwd, mode: calls.append((agent, text, cwd, mode)) or 7)
    return calls


def test_m1_projeto_inexistente_nao_cai_na_raiz(client, started):
    r = client.post("/dictation", json={"agent": "claude", "text": "rode", "project": "naoexiste"}).json()
    assert r == {"ok": False, "speech": "Não achei o projeto naoexiste."}
    assert "run_id" not in client.post("/dictation/confirm").json() and started == []


@pytest.mark.parametrize("project", ["..", "../x", ".", "a/../..", "C:\\Windows", "/etc"])
def test_m6_poc_project_fora_da_raiz_e_recusado(client, started, root, project):
    (root.parent / "x").mkdir(exist_ok=True)
    r = client.post("/dictation", json={"agent": "claude", "text": "rode", "project": project}).json()
    assert r["ok"] is False and r["speech"].startswith("Não achei o projeto")
    client.post("/dictation/confirm")
    assert started == []


def test_m1_politica_vem_do_cwd_final(client, started, root):
    (root / "alpha").mkdir()
    client.post("/mode", json={"mode": "auto"})
    client.post("/mode", json={"mode": "manual", "project": "alpha"})
    assert client.post("/dictation", json={"agent": "claude", "text": "rode", "project": "alpha"}).json()["ok"] is True
    assert client.post("/dictation/confirm").json()["run_id"] == 7
    agent, text, cwd, mode = started[0]
    assert os.path.realpath(cwd) == os.path.realpath(root / "alpha") and mode == "manual"


def test_m6_runs_sem_cwd_da_400(client):
    assert client.post("/runs", json={"agent": "claude", "prompt": "x"}).status_code == 400


def test_m6_runs_cwd_fora_da_raiz_da_400(client, started, root):
    outside = "C:\\Windows" if os.name == "nt" else "/etc"
    for cwd in (str(root.parent), str(root / ".."), outside, str(root / "nao-existe")):
        assert client.post("/runs", json={"agent": "claude", "prompt": "x", "cwd": cwd}).status_code == 400, cwd
    assert started == []


def test_m6_runs_politica_e_do_cwd_nao_do_project(client, started, root):
    """PoC: cwd=alpha com project=qualquer contornava a excecao 'alpha: manual'."""
    (root / "alpha").mkdir()
    client.post("/mode", json={"mode": "auto"})
    client.post("/mode", json={"mode": "manual", "project": "alpha"})
    r = client.post("/runs", json={"agent": "claude", "prompt": "x", "cwd": str(root / "alpha"), "project": "qualquer"})
    assert r.status_code == 200
    assert started[0][3] == "manual"
