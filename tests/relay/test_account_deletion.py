import pytest
from conftest import Machine, signup
from starlette.websockets import WebSocketDisconnect
from test_alexa_endpoint import alexa, link, world  # noqa: F401  (fixture reaproveitada)


def test_apagar_conta_exige_a_senha(world):  # noqa: F811
    c, env, clock, tf = world
    app_auth, _ = link(c)
    assert c.request("DELETE", "/v1/account", headers=app_auth, json={"password": "errada-errada"}).status_code == 403
    assert c.get("/v1/installations", headers=app_auth).status_code == 200  # nada foi apagado


def test_apagar_conta_remove_tudo_e_invalida_tokens(world):  # noqa: F811
    c, env, clock, tf = world
    app_auth, tok = link(c)
    m = Machine(c, app_auth, tf.mktemp("m"), clock)
    alexa(c, env, clock, token=tok)
    r = c.request("DELETE", "/v1/account", headers=app_auth, json={"password": "senha-bem-longa"})
    assert r.status_code == 204
    assert c.get("/v1/installations", headers=app_auth).status_code == 401  # sessao do app
    assert c.get("/v1/installations", headers={"Authorization": "Bearer " + tok}).status_code == 401  # token OAuth
    assert c.post("/v1/login", json={"email": "a@exemplo.com", "password": "senha-bem-longa"}).status_code == 401
    ws = c.websocket_connect("/v1/connect")
    s = ws.__enter__()
    s.send_json(m.envelope())  # a instalacao tambem deixou de existir
    with pytest.raises(WebSocketDisconnect):
        s.receive_json()
    ws.__exit__(None, None, None)


def test_apagar_conta_derruba_a_conexao_ativa(world):  # noqa: F811
    c, env, clock, tf = world
    app_auth, _ = link(c)
    m = Machine(c, app_auth, tf.mktemp("m"), clock)
    ws = c.websocket_connect("/v1/connect")
    s = ws.__enter__()
    try:
        s.send_json(m.envelope())
        s.receive_json()
        c.request("DELETE", "/v1/account", headers=app_auth, json={"password": "senha-bem-longa"})
        with pytest.raises(WebSocketDisconnect):
            s.receive_json()
    finally:
        ws.__exit__(None, None, None)


def test_apagar_conta_de_a_nao_toca_a_conta_de_b(world):  # noqa: F811
    c, env, clock, tf = world
    a_auth, _ = link(c, "a@exemplo.com")
    b_auth, b_tok = link(c, "b@exemplo.com")
    Machine(c, b_auth, tf.mktemp("b"), clock)
    c.request("DELETE", "/v1/account", headers=a_auth, json={"password": "senha-bem-longa"})
    assert len(c.get("/v1/installations", headers=b_auth).json()) == 1
    assert c.get("/v1/installations", headers={"Authorization": "Bearer " + b_tok}).status_code == 200


def test_email_pode_ser_cadastrado_de_novo_depois_de_apagar(world):  # noqa: F811
    c, env, clock, tf = world
    a_auth, _ = link(c)
    c.request("DELETE", "/v1/account", headers=a_auth, json={"password": "senha-bem-longa"})
    assert signup(c, "a@exemplo.com")
