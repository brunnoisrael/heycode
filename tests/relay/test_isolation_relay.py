import pytest
from conftest import Machine, signup


@pytest.fixture
def duas_contas(client, tmp_path_factory, clock):
    a = signup(client, "a@exemplo.com")
    b = signup(client, "b@exemplo.com")
    ma = Machine(client, a, tmp_path_factory.mktemp("a"), clock, "do-a")
    mb = Machine(client, b, tmp_path_factory.mktemp("b"), clock, "do-b")
    return client, a, b, ma, mb


def test_skill_de_a_nao_alcanca_instalacao_de_b(duas_contas):
    client, a, b, ma, mb = duas_contas
    r = client.post("/v1/skill/request", headers=a, json={"installation_id": mb.id, "text": "oi", "destination": "p"})
    assert r.status_code == 404
    r = client.post(
        "/v1/skill/request", headers=a, json={"installation_id": "nao-existe", "text": "oi", "destination": "p"}
    )
    assert r.status_code == 404  # mesma resposta: nao revela se a instalacao existe


def test_sem_instalacao_informada_usa_so_as_da_propria_conta(duas_contas):
    client, a, b, ma, mb = duas_contas
    r = client.post("/v1/skill/request", headers=a, json={"text": "oi", "destination": "p"})
    assert r.json() == {"state": "offline"}  # resolveu para a de A (offline), nunca a de B


def test_conta_sem_instalacao_recebe_erro_claro(client):
    a = signup(client, "a@exemplo.com")
    r = client.post("/v1/skill/request", headers=a, json={"text": "oi", "destination": "p"})
    assert r.status_code == 404 and r.json()["detail"] == "no_installation"


def test_varias_instalacoes_exigem_escolha(client, tmp_path_factory, clock):
    a = signup(client, "a@exemplo.com")
    m1 = Machine(client, a, tmp_path_factory.mktemp("1"), clock, "um")
    m2 = Machine(client, a, tmp_path_factory.mktemp("2"), clock, "dois")
    r = client.post("/v1/skill/request", headers=a, json={"text": "oi", "destination": "p"})
    assert r.status_code == 409 and r.json()["detail"] == "choose_installation"
    r = client.post("/v1/skill/request", headers=a, json={"installation_id": m2.id, "text": "oi", "destination": "p"})
    assert r.json() == {"state": "offline"}
    assert m1.id != m2.id


def test_resultado_de_a_nao_e_lido_por_b(make_client, tmp_path_factory, clock):
    client = make_client(sync_timeout=0.1)
    a = signup(client, "a@exemplo.com")
    b = signup(client, "b@exemplo.com")
    ma = Machine(client, a, tmp_path_factory.mktemp("a"), clock)
    with client.websocket_connect("/v1/connect") as s:
        s.send_json(ma.envelope())
        s.receive_json()
        rid = client.post("/v1/skill/request", headers=a, json={"text": "x", "destination": "p"}).json()["request_id"]
        assert client.get(f"/v1/skill/result/{rid}", headers=b).status_code == 404
        assert client.get(f"/v1/skill/result/{rid}", headers=a).status_code == 200


def test_maquina_nao_resolve_pedido_de_outra_conta(make_client, tmp_path_factory, clock):
    """A maquina de B responde com in_reply_to de um pedido da conta A: o relay ignora."""
    client = make_client(sync_timeout=0.1)
    a = signup(client, "a@exemplo.com")
    b = signup(client, "b@exemplo.com")
    ma = Machine(client, a, tmp_path_factory.mktemp("a"), clock)
    mb = Machine(client, b, tmp_path_factory.mktemp("b"), clock)
    with client.websocket_connect("/v1/connect") as sa, client.websocket_connect("/v1/connect") as sb:
        sa.send_json(ma.envelope())
        sa.receive_json()
        sb.send_json(mb.envelope())
        sb.receive_json()
        rid = client.post("/v1/skill/request", headers=a, json={"text": "x", "destination": "p"}).json()["request_id"]
        sb.send_json(
            mb.envelope("run-result", {"run_id": "1", "state": "done", "summary": "forjado", "in_reply_to": rid})
        )
        # um envelope valido da propria maquina de B ainda e aceito, mas nao resolve o pedido de A
        assert client.get(f"/v1/skill/result/{rid}", headers=a).json() == {"state": "pending"}


def test_cota_diaria_conta_pedidos_e_zera_no_dia_seguinte(make_client, tmp_path, clock):
    client = make_client(daily_quota=3)
    a = signup(client, "a@exemplo.com")
    Machine(client, a, tmp_path, clock)
    body = {"text": "x", "destination": "p"}
    for _ in range(3):
        assert client.post("/v1/skill/request", headers=a, json=body).json() == {"state": "offline"}
    r = client.post("/v1/skill/request", headers=a, json=body)
    assert r.status_code == 429 and r.json()["detail"] == "quota_requests"
    clock.t += 86400
    token = client.post("/v1/login", json={"email": "a@exemplo.com", "password": "senha-bem-longa"}).json()["token"]
    a = {"Authorization": "Bearer " + token}  # a sessao de 12 h expirou junto
    assert client.post("/v1/skill/request", headers=a, json=body).json() == {"state": "offline"}


def test_login_tem_limite_de_taxa_por_origem(client):
    for _ in range(10):
        assert client.post("/v1/login", json={"email": "x@exemplo.com", "password": "errada-errada"}).status_code == 401
    assert client.post("/v1/login", json={"email": "x@exemplo.com", "password": "errada-errada"}).status_code == 429


def test_logs_do_relay_nao_contem_segredo(client, caplog):
    import logging

    caplog.set_level(logging.DEBUG)
    a = signup(client, "a@exemplo.com")
    client.post("/v1/skill/request", headers=a, json={"text": "token ghp_" + "a" * 36, "destination": "p"})
    assert "ghp_" not in caplog.text and "senha-bem-longa" not in caplog.text
