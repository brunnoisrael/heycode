import time


def _seed(client):
    store = client.server.store
    a1 = store.add_approval("claude", "api", "Bash", "ls -la", "s1")
    store.resolve_approval(a1, "allow")
    a2 = store.add_approval("codex", "web", "Bash", "curl -H 'Authorization: Bearer abcdef123456' https://x", "s2")
    store.resolve_approval(a2, "deny")
    store.add_approval("claude", "api", "Bash", "rm -rf build", "s3")  # segue pendente
    rid = store.create_run("claude", "api", "rode os testes com a chave ghp_" + "a" * 36, ".")
    store.update_run(rid, status="concluida", summary="tudo certo, token ghp_" + "b" * 36)


def test_exige_o_segredo_de_controle(client):
    assert client.get("/voice/audit", headers={"x-secret": "errado"}).status_code in (401, 403)
    assert client.get("/voice/audit", headers=client.agent_h).status_code in (401, 403)  # segredo de agente nao serve


def test_devolve_aprovacoes_e_execucoes_recentes_com_segredos_mascarados(client):
    _seed(client)
    body = client.get("/voice/audit?limit=10").json()
    decisions = [a["decision"] for a in body["approvals"]]
    assert decisions == ["pending", "deny", "allow"]  # mais recente primeiro; sem decisao = pending
    texto = str(body)
    assert "abcdef123456" not in texto and "ghp_" not in texto
    assert body["approvals"][2]["command"] == "ls -la" and body["approvals"][2]["agent"] == "claude"
    assert body["runs"][0]["status"] == "concluida" and body["runs"][0]["project"] == "api"
    assert set(body["approvals"][0]) == {"id", "agent", "project", "tool", "command", "decision", "t"}


def test_limite_e_limitado_entre_1_e_50(client):
    for i in range(60):
        client.server.store.add_approval("claude", "p", "Bash", f"echo {i}", "s")
    assert len(client.get("/voice/audit?limit=500").json()["approvals"]) == 50
    assert len(client.get("/voice/audit?limit=0").json()["approvals"]) == 1
    assert len(client.get("/voice/audit?limit=3").json()["approvals"]) == 3
    assert len(client.get("/voice/audit").json()["approvals"]) == 20  # padrao


def test_nao_vaza_a_resposta_livre_nem_o_texto_da_pergunta(client):
    store = client.server.store
    qid = store.add_approval("claude", "api", "pedir_resposta", "Qual a senha do banco?", "s9")
    store.answer_question(qid, "hunter2-super-secreta", max_age=1e9)
    assert "hunter2" not in str(client.get("/voice/audit").json())
    assert time.time() > 0
