import base64
import hashlib
from urllib.parse import parse_qs, urlparse

import pytest
from conftest import Clock, signup
from fastapi.testclient import TestClient

from heycode.relay.app import OAuthConfig, create_app
from heycode.relay.repo import SqliteRepository

REDIRECT = "https://pitangui.amazon.com/api/skill/link/M2TEST"
CFG = OAuthConfig(client_id="alexa-client", client_secret="segredo-do-cliente", redirect_uris=(REDIRECT,))


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def client(clock):
    with TestClient(create_app(SqliteRepository(":memory:"), clock, oauth=CFG), follow_redirects=False) as c:
        yield c


def authorize(client, email="a@exemplo.com", password="senha-bem-longa", **over):
    params = {"client_id": "alexa-client", "redirect_uri": REDIRECT, "state": "xyz", "response_type": "code"}
    params.update(over.pop("params", {}))
    body = {"email": email, "password": password, **params, **over}
    return client.post("/oauth/authorize", data=body)


def get_code(client, **kw):
    r = authorize(client, **kw)
    assert r.status_code == 302, r.text
    q = parse_qs(urlparse(r.headers["location"]).query)
    assert q["state"] == ["xyz"]
    return q["code"][0]


def token(client, **over):
    data = {
        "grant_type": "authorization_code",
        "client_id": "alexa-client",
        "client_secret": "segredo-do-cliente",
        "redirect_uri": REDIRECT,
    }
    data.update(over)
    return client.post("/oauth/token", data=data)


def test_formulario_de_login_so_para_cliente_e_redirect_validos(client):
    ok = client.get("/oauth/authorize", params={"client_id": "alexa-client", "redirect_uri": REDIRECT, "state": "s"})
    assert ok.status_code == 200 and "<form" in ok.text and 'value="s"' in ok.text
    bad = client.get("/oauth/authorize", params={"client_id": "outro", "redirect_uri": REDIRECT, "state": "s"})
    assert bad.status_code == 400


def test_parametros_do_formulario_sao_escapados(client):
    r = client.get(
        "/oauth/authorize",
        params={"client_id": "alexa-client", "redirect_uri": REDIRECT, "state": '"><script>x</script>'},
    )
    assert "<script>x" not in r.text


def test_fluxo_completo_autorizar_trocar_e_usar_o_token(client):
    signup(client, "a@exemplo.com")
    code = get_code(client)
    r = token(client, code=code)
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"].lower() == "bearer" and body["expires_in"] == 3600 and body["refresh_token"]
    auth = {"Authorization": "Bearer " + body["access_token"]}
    assert client.get("/v1/installations", headers=auth).status_code == 200  # a skill usa o token do OAuth


def test_redirect_uri_fora_da_lista_nao_redireciona(client):
    signup(client, "a@exemplo.com")
    r = authorize(client, params={"redirect_uri": "https://evil.example/cb"})
    assert r.status_code == 400 and "location" not in r.headers


def test_login_errado_nao_gera_codigo(client):
    signup(client, "a@exemplo.com")
    r = authorize(client, password="senha-errada-aqui")
    assert r.status_code == 401 and "location" not in r.headers


def test_codigo_de_uso_unico(client):
    signup(client, "a@exemplo.com")
    code = get_code(client)
    assert token(client, code=code).status_code == 200
    r = token(client, code=code)
    assert r.status_code == 400 and r.json()["error"] == "invalid_grant"


def test_codigo_expira_em_10_min(client, clock):
    signup(client, "a@exemplo.com")
    code = get_code(client)
    clock.t += 601
    assert token(client, code=code).json()["error"] == "invalid_grant"


def test_codigo_nao_vale_com_outro_redirect_uri(client):
    signup(client, "a@exemplo.com")
    code = get_code(client)
    assert token(client, code=code, redirect_uri="https://evil.example/cb").json()["error"] == "invalid_grant"


def test_segredo_do_cliente_errado_recusado(client):
    signup(client, "a@exemplo.com")
    code = get_code(client)
    r = token(client, code=code, client_secret="errado")
    assert r.status_code == 401 and r.json()["error"] == "invalid_client"
    assert token(client, code=code).status_code == 200  # a tentativa errada nao gastou o codigo


def test_cliente_basic_auth_tambem_funciona(client):
    signup(client, "a@exemplo.com")
    code = get_code(client)
    basic = base64.b64encode(b"alexa-client:segredo-do-cliente").decode()
    r = client.post(
        "/oauth/token",
        data={"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT},
        headers={"Authorization": "Basic " + basic},
    )
    assert r.status_code == 200


def test_pkce_s256(client):
    signup(client, "a@exemplo.com")
    verifier = "v" * 50
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    code = get_code(client, params={"code_challenge": challenge, "code_challenge_method": "S256"})
    assert token(client, code=code, code_verifier="errado" * 10).json()["error"] == "invalid_grant"
    code = get_code(client, params={"code_challenge": challenge, "code_challenge_method": "S256"})
    assert token(client, code=code, code_verifier=verifier).status_code == 200


def test_access_token_expira_em_1h(client, clock):
    signup(client, "a@exemplo.com")
    at = token(client, code=get_code(client)).json()["access_token"]
    auth = {"Authorization": "Bearer " + at}
    clock.t += 3599
    assert client.get("/v1/installations", headers=auth).status_code == 200
    clock.t += 2
    assert client.get("/v1/installations", headers=auth).status_code == 401


def test_refresh_rotaciona_e_o_antigo_deixa_de_valer(client):
    signup(client, "a@exemplo.com")
    first = token(client, code=get_code(client)).json()
    r = token(client, grant_type="refresh_token", refresh_token=first["refresh_token"])
    assert r.status_code == 200
    second = r.json()
    assert second["refresh_token"] != first["refresh_token"] and second["access_token"] != first["access_token"]
    reuse = token(client, grant_type="refresh_token", refresh_token=first["refresh_token"])
    assert reuse.status_code == 400 and reuse.json()["error"] == "invalid_grant"


def test_reuso_de_refresh_revoga_a_familia_inteira(client):
    signup(client, "a@exemplo.com")
    first = token(client, code=get_code(client)).json()
    second = token(client, grant_type="refresh_token", refresh_token=first["refresh_token"]).json()
    token(client, grant_type="refresh_token", refresh_token=first["refresh_token"])  # reuso: alarme
    assert token(client, grant_type="refresh_token", refresh_token=second["refresh_token"]).status_code == 400
    auth = {"Authorization": "Bearer " + second["access_token"]}
    assert client.get("/v1/installations", headers=auth).status_code == 401


def test_refresh_expira_em_30_dias(client, clock):
    signup(client, "a@exemplo.com")
    first = token(client, code=get_code(client)).json()
    clock.t += 30 * 86400 + 1
    assert token(client, grant_type="refresh_token", refresh_token=first["refresh_token"]).status_code == 400


def test_access_token_nao_serve_como_refresh_e_vice_versa(client):
    signup(client, "a@exemplo.com")
    t = token(client, code=get_code(client)).json()
    assert token(client, grant_type="refresh_token", refresh_token=t["access_token"]).status_code == 400
    auth = {"Authorization": "Bearer " + t["refresh_token"]}
    assert client.get("/v1/installations", headers=auth).status_code == 401


def test_tokens_guardados_so_como_hash(clock):
    repo = SqliteRepository(":memory:")
    with TestClient(create_app(repo, clock, oauth=CFG), follow_redirects=False) as c:
        signup(c, "a@exemplo.com")
        t = token(c, code=get_code(c)).json()
    guardado = repo.dump_oauth_hashes()
    assert t["access_token"] not in guardado and t["refresh_token"] not in guardado and len(guardado) == 2


def test_grant_type_desconhecido_recusado(client):
    assert token(client, grant_type="password", username="a", password="b").json()["error"] == "unsupported_grant_type"


def test_oauth_nao_configurado_responde_404(clock):
    with TestClient(create_app(SqliteRepository(":memory:"), clock)) as c:
        assert c.get("/oauth/authorize").status_code == 404
        assert c.post("/oauth/token", data={}).status_code == 404


def test_token_tem_limite_por_ip(client, clock):
    for _ in range(30):
        assert token(client, code="invalido").status_code == 400
    r = token(client, code="invalido")
    assert r.status_code == 429 and r.headers["retry-after"] == "60"
    clock.t += 61
    assert token(client, code="invalido").status_code == 400


def test_formulario_de_vinculacao_tem_limite_por_ip_e_por_email(client, clock):
    signup(client, "a@exemplo.com")
    clock.t += 61
    for _ in range(10):
        assert authorize(client, password="senha-errada-1").status_code == 401
    r = authorize(client)
    assert r.status_code == 429 and "Muitas tentativas" in r.text and int(r.headers["retry-after"]) > 0
