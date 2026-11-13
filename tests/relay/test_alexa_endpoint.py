import datetime as dt
import json
from urllib.parse import parse_qs, urlparse

import pytest
from conftest import Clock, Machine, signup
from fastapi.testclient import TestClient
from test_alexa_verify import NOW, SKILL, URL, Env, sign

from heycode.relay.alexa_verify import AlexaVerifier
from heycode.relay.app import OAuthConfig, create_app
from heycode.relay.repo import SqliteRepository

REDIRECT = "https://pitangui.amazon.com/api/skill/link/M2TEST"
CFG = OAuthConfig("alexa-client", "segredo-do-cliente", (REDIRECT,))


@pytest.fixture
def world(tmp_path_factory):
    env = Env()
    clock = Clock(NOW)
    verifier = AlexaVerifier(SKILL, clock, fetch=env.fetch, trust_roots=[env.ca])
    repo = SqliteRepository(":memory:")
    with TestClient(create_app(repo, clock, oauth=CFG, alexa=verifier), follow_redirects=False) as c:
        yield c, env, clock, tmp_path_factory


def link(client, email="a@exemplo.com"):
    """Cadastra, faz o account linking e devolve (cabecalho do app, token OAuth da Alexa)."""
    app_auth = signup(client, email)
    r = client.post(
        "/oauth/authorize",
        data={
            "email": email,
            "password": "senha-bem-longa",
            "client_id": "alexa-client",
            "redirect_uri": REDIRECT,
            "state": "s",
        },
    )
    code = parse_qs(urlparse(r.headers["location"]).query)["code"][0]
    tok = client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT,
            "client_id": "alexa-client",
            "client_secret": "segredo-do-cliente",
        },
    ).json()["access_token"]
    return app_auth, tok


def alexa(client, env, clock, *, token=None, device="amzn1.ask.device.A", intent=None, rtype=None, signature=None):
    ts = dt.datetime.fromtimestamp(clock(), dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    system = {"application": {"applicationId": SKILL}}
    if token:
        system["user"] = {"accessToken": token}
    if device:
        system["device"] = {"deviceId": device}
    request = {"type": rtype or ("IntentRequest" if intent else "LaunchRequest"), "timestamp": ts}
    if intent:
        request["intent"] = {"name": intent}
    body = json.dumps({"version": "1.0", "context": {"System": system}, "request": request}).encode()
    headers = {
        "signaturecertchainurl": URL,
        "signature-256": signature or sign(env.leaf_key, body),
        "content-type": "application/json",
    }
    return client.post("/v1/alexa", content=body, headers=headers)


def speech(r):
    return r.json()["response"]["outputSpeech"]["text"]


def test_endpoint_nao_configurado_responde_404(tmp_path):
    with TestClient(create_app(SqliteRepository(":memory:"), Clock())) as c:
        assert c.post("/v1/alexa", content=b"{}").status_code == 404


def test_assinatura_invalida_e_400_e_nada_e_registrado(world):
    c, env, clock, _ = world
    app_auth, tok = link(c)
    r = alexa(c, env, clock, token=tok, signature="AAAA")
    assert r.status_code == 400 and r.json()["error"] == "bad_signature"
    assert c.get("/v1/devices", headers=app_auth).json() == []


def test_sem_vinculo_pede_para_vincular_a_conta(world):
    c, env, clock, _ = world
    r = alexa(c, env, clock)
    assert r.status_code == 200
    assert r.json()["response"]["card"]["type"] == "LinkAccount"
    assert r.json()["response"]["shouldEndSession"] is True


def test_token_invalido_tambem_pede_vinculo(world):
    c, env, clock, _ = world
    assert alexa(c, env, clock, token="inventado").json()["response"]["card"]["type"] == "LinkAccount"


def test_conta_sem_computador_pareado_explica(world):
    c, env, clock, _ = world
    _, tok = link(c)
    assert "computador" in speech(alexa(c, env, clock, token=tok)).lower()


def test_dispositivo_novo_nao_executa_e_vira_solicitacao_pendente(world):
    c, env, clock, tf = world
    app_auth, tok = link(c)
    m = Machine(c, app_auth, tf.mktemp("m"), clock)
    r = alexa(c, env, clock, token=tok)
    assert "autor" in speech(r).lower() and "aplicativo" in speech(r).lower()
    devs = c.get("/v1/devices", headers=app_auth).json()
    assert devs == [{"installation_id": m.id, "device_id": "amzn1.ask.device.A", "status": "pending"}]
    assert alexa(c, env, clock, token=tok, intent="StatusIntent").json()["response"]["shouldEndSession"] is True


def test_aprovado_e_computador_offline_diz_que_esta_offline(world):
    c, env, clock, tf = world
    app_auth, tok = link(c)
    m = Machine(c, app_auth, tf.mktemp("m"), clock, "notebook")
    alexa(c, env, clock, token=tok)
    assert (
        c.post(
            "/v1/devices/approve", headers=app_auth, json={"installation_id": m.id, "device_id": "amzn1.ask.device.A"}
        ).status_code
        == 204
    )
    assert "offline" in speech(alexa(c, env, clock, token=tok))


def test_aprovado_e_computador_conectado_diz_conectado(world):
    c, env, clock, tf = world
    app_auth, tok = link(c)
    m = Machine(c, app_auth, tf.mktemp("m"), clock, "notebook")
    alexa(c, env, clock, token=tok)
    c.post("/v1/devices/approve", headers=app_auth, json={"installation_id": m.id, "device_id": "amzn1.ask.device.A"})
    with c.websocket_connect("/v1/connect") as ws:
        ws.send_json(m.envelope())
        ws.receive_json()
        out = speech(alexa(c, env, clock, token=tok))
    assert "conectado" in out and "notebook" in out


def test_so_a_conta_dona_aprova_o_dispositivo(world):
    c, env, clock, tf = world
    a_auth, a_tok = link(c, "a@exemplo.com")
    b_auth, b_tok = link(c, "b@exemplo.com")
    ma = Machine(c, a_auth, tf.mktemp("a"), clock)
    alexa(c, env, clock, token=a_tok)
    body = {"installation_id": ma.id, "device_id": "amzn1.ask.device.A"}
    assert c.post("/v1/devices/approve", headers=b_auth, json=body).status_code == 404
    assert c.get("/v1/devices", headers=b_auth).json() == []


def test_aprovar_exige_solicitacao_pendente(world):
    c, env, clock, tf = world
    app_auth, _ = link(c)
    m = Machine(c, app_auth, tf.mktemp("m"), clock)
    r = c.post("/v1/devices/approve", headers=app_auth, json={"installation_id": m.id, "device_id": "nunca-visto"})
    assert r.status_code == 404


def test_dispositivo_aprovado_para_a_nao_vale_para_b(world):
    c, env, clock, tf = world
    a_auth, a_tok = link(c, "a@exemplo.com")
    b_auth, b_tok = link(c, "b@exemplo.com")
    ma = Machine(c, a_auth, tf.mktemp("a"), clock)
    mb = Machine(c, b_auth, tf.mktemp("b"), clock)
    alexa(c, env, clock, token=a_tok)
    c.post("/v1/devices/approve", headers=a_auth, json={"installation_id": ma.id, "device_id": "amzn1.ask.device.A"})
    out = alexa(c, env, clock, token=b_tok)  # o mesmo Echo, na conta de B
    assert "autor" in speech(out).lower()
    assert c.get("/v1/devices", headers=b_auth).json()[0]["status"] == "pending"
    assert mb.id


def test_revogar_dispositivo_volta_a_exigir_aprovacao(world):
    c, env, clock, tf = world
    app_auth, tok = link(c)
    m = Machine(c, app_auth, tf.mktemp("m"), clock)
    alexa(c, env, clock, token=tok)
    c.post("/v1/devices/approve", headers=app_auth, json={"installation_id": m.id, "device_id": "amzn1.ask.device.A"})
    assert c.delete(f"/v1/devices/{m.id}/amzn1.ask.device.A", headers=app_auth).status_code == 204
    assert "autor" in speech(alexa(c, env, clock, token=tok)).lower()


def test_negar_remove_a_solicitacao(world):
    c, env, clock, tf = world
    app_auth, tok = link(c)
    m = Machine(c, app_auth, tf.mktemp("m"), clock)
    alexa(c, env, clock, token=tok)
    r = c.post("/v1/devices/deny", headers=app_auth, json={"installation_id": m.id, "device_id": "amzn1.ask.device.A"})
    assert r.status_code == 204 and c.get("/v1/devices", headers=app_auth).json() == []


def test_varias_instalacoes_sem_padrao_pedem_escolha_e_com_padrao_roteiam(world):
    c, env, clock, tf = world
    app_auth, tok = link(c)
    m1 = Machine(c, app_auth, tf.mktemp("1"), clock, "um")
    m2 = Machine(c, app_auth, tf.mktemp("2"), clock, "dois")
    assert "escolha" in speech(alexa(c, env, clock, token=tok)).lower()
    assert c.get("/v1/devices", headers=app_auth).json() == []  # nada foi registrado sem destino
    assert c.put("/v1/default-installation", headers=app_auth, json={"installation_id": m2.id}).status_code == 204
    alexa(c, env, clock, token=tok)
    assert c.get("/v1/devices", headers=app_auth).json()[0]["installation_id"] == m2.id
    assert m1.id != m2.id


def test_instalacao_padrao_de_outra_conta_recusada(world):
    c, env, clock, tf = world
    a_auth, _ = link(c, "a@exemplo.com")
    b_auth, _ = link(c, "b@exemplo.com")
    ma = Machine(c, a_auth, tf.mktemp("a"), clock)
    assert c.put("/v1/default-installation", headers=b_auth, json={"installation_id": ma.id}).status_code == 404


def test_padrao_revogada_volta_a_pedir_escolha(world):
    c, env, clock, tf = world
    app_auth, tok = link(c)
    m1 = Machine(c, app_auth, tf.mktemp("1"), clock, "um")
    Machine(c, app_auth, tf.mktemp("2"), clock, "dois")
    c.put("/v1/default-installation", headers=app_auth, json={"installation_id": m1.id})
    c.delete(f"/v1/installations/{m1.id}", headers=app_auth)
    out = speech(alexa(c, env, clock, token=tok))
    assert "autor" in out.lower() or "escolha" in out.lower()  # sobrou uma so: usa essa, sem a revogada


def test_sem_device_id_recusa_sem_executar(world):
    c, env, clock, tf = world
    app_auth, tok = link(c)
    Machine(c, app_auth, tf.mktemp("m"), clock)
    out = alexa(c, env, clock, token=tok, device=None)
    assert out.json()["response"]["shouldEndSession"] is True
    assert c.get("/v1/devices", headers=app_auth).json() == []


def test_solicitacoes_pendentes_tem_limite(world):
    c, env, clock, tf = world
    app_auth, tok = link(c)
    Machine(c, app_auth, tf.mktemp("m"), clock)
    for i in range(15):
        alexa(c, env, clock, token=tok, device=f"amzn1.ask.device.{i}")
    assert len(c.get("/v1/devices", headers=app_auth).json()) == 10


def _aprovada(world):
    c, env, clock, tf = world
    app_auth, tok = link(c)
    m = Machine(c, app_auth, tf.mktemp("m"), clock)
    alexa(c, env, clock, token=tok)
    c.post("/v1/devices/approve", headers=app_auth, json={"installation_id": m.id, "device_id": "amzn1.ask.device.A"})
    return c, env, clock, tok


def test_ajuda_parar_e_intents_ainda_nao_suportadas(world):
    c, env, clock, tok = _aprovada(world)
    assert "HeyCode" in speech(alexa(c, env, clock, token=tok, intent="AMAZON.HelpIntent"))
    stop = alexa(c, env, clock, token=tok, intent="AMAZON.StopIntent")
    assert stop.json()["response"]["shouldEndSession"] is True
    nao = alexa(c, env, clock, token=tok, intent="ApproveIntent")
    assert "ainda" in speech(nao) and nao.json()["response"]["shouldEndSession"] is True


def test_fim_de_sessao_responde_vazio(world):
    c, env, clock, tok = _aprovada(world)
    r = alexa(c, env, clock, token=tok, rtype="SessionEndedRequest")
    assert r.status_code == 200 and "outputSpeech" not in r.json()["response"]
