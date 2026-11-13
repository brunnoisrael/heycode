import pytest
from conftest import Clock, signup
from fastapi.testclient import TestClient

from heycode.relay.app import create_app
from heycode.relay.repo import SqliteRepository

PW = "senha-bem-longa"


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def client(clock):
    # https de verdade para o cookie Secure voltar nas requisicoes seguintes
    with TestClient(create_app(SqliteRepository(":memory:"), clock), base_url="https://relay.exemplo") as c:
        yield c


def panel_login(client, email="a@exemplo.com", password=PW):
    return client.post("/v1/panel/login", json={"email": email, "password": password})


def csrf(client):
    return client.get("/v1/panel/session").json()["csrf"]


def test_login_define_cookie_httponly_secure_samesite_strict(client):
    signup(client, "a@exemplo.com")
    client.cookies.clear()
    r = panel_login(client)
    assert r.status_code == 200
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "secure" in cookie and "samesite=strict" in cookie and "path=/" in cookie
    assert "token" not in r.json()  # o painel nunca recebe o token da sessao no corpo


def test_login_errado_e_generico_e_nao_define_cookie(client):
    signup(client, "a@exemplo.com")
    client.cookies.clear()
    r1 = panel_login(client, password="errada-errada")
    r2 = panel_login(client, email="x@exemplo.com", password="errada-errada")
    assert r1.status_code == r2.status_code == 401 and r1.json() == r2.json()
    assert "set-cookie" not in r1.headers


def test_leitura_com_cookie_funciona_sem_csrf(client):
    signup(client, "a@exemplo.com")
    client.cookies.clear()
    panel_login(client)
    assert client.get("/v1/installations").status_code == 200


def test_escrita_com_cookie_sem_csrf_ou_com_csrf_errado_e_recusada(client):
    signup(client, "a@exemplo.com")
    client.cookies.clear()
    panel_login(client)
    assert client.post("/v1/pair/codes").status_code == 403
    assert client.post("/v1/pair/codes", headers={"X-CSRF-Token": "errado"}).status_code == 403
    ok = client.post("/v1/pair/codes", headers={"X-CSRF-Token": csrf(client)})
    assert ok.status_code == 200 and len(ok.json()["code"]) == 8


def test_csrf_de_outra_sessao_nao_vale(client):
    signup(client, "a@exemplo.com")
    client.cookies.clear()
    panel_login(client)
    token_da_primeira = csrf(client)
    client.cookies.clear()
    panel_login(client)  # segunda sessao
    assert client.post("/v1/pair/codes", headers={"X-CSRF-Token": token_da_primeira}).status_code == 403


def test_bearer_continua_funcionando_sem_csrf(client):
    auth = signup(client, "a@exemplo.com")
    client.cookies.clear()
    assert client.post("/v1/pair/codes", headers=auth).status_code == 200


def test_sem_cookie_nem_bearer_e_401(client):
    assert client.get("/v1/installations").status_code == 401
    assert client.get("/v1/panel/session").status_code == 401


def test_sessao_devolve_email_e_csrf(client):
    signup(client, "a@exemplo.com")
    client.cookies.clear()
    panel_login(client, email="A@Exemplo.com")
    body = client.get("/v1/panel/session").json()
    assert body["email"] == "a@exemplo.com" and len(body["csrf"]) >= 32


def test_logout_invalida_no_servidor_e_limpa_o_cookie(client):
    signup(client, "a@exemplo.com")
    client.cookies.clear()
    panel_login(client)
    stolen = client.cookies.get("hc_session")
    assert client.post("/v1/panel/logout").status_code == 403  # logout tambem e escrita: exige CSRF
    r = client.post("/v1/panel/logout", headers={"X-CSRF-Token": csrf(client)})
    assert r.status_code == 204 and "max-age=0" in r.headers["set-cookie"].lower()
    client.cookies.clear()
    client.cookies.set("hc_session", stolen)  # mesmo copiando o cookie, a sessao morreu
    assert client.get("/v1/installations").status_code == 401


def test_sessao_expirada_no_cookie_e_401(client, clock):
    signup(client, "a@exemplo.com")
    client.cookies.clear()
    panel_login(client)
    clock.t += 13 * 3600
    assert client.get("/v1/installations").status_code == 401


def test_cookie_de_a_nao_enxerga_dados_de_b(client):
    a = signup(client, "a@exemplo.com")
    b = signup(client, "b@exemplo.com")
    client.cookies.clear()
    code = client.post("/v1/pair/codes", headers=a).json()["code"]
    assert code
    panel_login(client, email="b@exemplo.com")
    assert client.get("/v1/installations").json() == []
    assert client.get("/v1/pair/pending").json() == []
    assert b


def test_cabecalhos_de_seguranca_em_todas_as_respostas(client):
    r = client.get("/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["referrer-policy"] == "no-referrer"
    r = client.get("/v1/installations")  # ate o 401
    assert r.headers["x-content-type-options"] == "nosniff"
    assert "no-store" in client.get("/v1/panel/session").headers["cache-control"]


def test_login_do_painel_tem_limite_de_taxa(client):
    for _ in range(10):
        assert panel_login(client, password="errada-errada").status_code == 401
    assert panel_login(client, password="errada-errada").status_code == 429
