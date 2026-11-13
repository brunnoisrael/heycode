import pytest
from fastapi.testclient import TestClient

from heycode.relay.app import create_app
from heycode.relay.repo import SqliteRepository


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def client(clock):
    return TestClient(create_app(SqliteRepository(":memory:"), clock))


def signup(client, email):
    assert client.post("/v1/register", json={"email": email, "password": "senha-bem-longa"}).status_code == 201
    r = client.post("/v1/login", json={"email": email, "password": "senha-bem-longa"})
    assert r.status_code == 200
    return {"Authorization": "Bearer " + r.json()["token"]}


def pair(client, auth, pub="pub-1", name="notebook"):
    code = client.post("/v1/pair/codes", headers=auth).json()["code"]
    r = client.post("/v1/pair/redeem", json={"code": code, "public_key": pub, "name": name})
    assert r.status_code == 200, r.text
    pid = r.json()["pending_id"]
    assert client.post("/v1/pair/machine-confirm", json={"pending_id": pid}).status_code == 200
    done = client.post("/v1/pair/confirm", headers=auth, json={"pending_id": pid})
    assert done.status_code == 200, done.text
    return pid, done.json()


def test_rotas_protegidas_exigem_login(client):
    assert client.post("/v1/pair/codes").status_code == 401
    assert client.get("/v1/installations").status_code == 401
    assert client.get("/v1/installations", headers={"Authorization": "Bearer inventado"}).status_code == 401


def test_login_errado_devolve_401_generico(client):
    signup(client, "a@exemplo.com")
    r1 = client.post("/v1/login", json={"email": "a@exemplo.com", "password": "errada-errada"})
    r2 = client.post("/v1/login", json={"email": "x@exemplo.com", "password": "errada-errada"})
    assert r1.status_code == r2.status_code == 401 and r1.json() == r2.json()


def test_emitir_resgatar_e_confirmar_cria_instalacao(client):
    auth = signup(client, "a@exemplo.com")
    pid, body = pair(client, auth)
    assert body["installation_id"]
    lst = client.get("/v1/installations", headers=auth).json()
    assert [i["name"] for i in lst] == ["notebook"]
    status = client.get(f"/v1/pair/{pid}").json()
    assert status == {"state": "done", "installation_id": body["installation_id"]}


def test_codigo_de_verificacao_igual_nos_dois_lados(client):
    auth = signup(client, "a@exemplo.com")
    code = client.post("/v1/pair/codes", headers=auth).json()["code"]
    machine = client.post("/v1/pair/redeem", json={"code": code, "public_key": "pub-1", "name": "n"}).json()
    seen = client.get(f"/v1/pair/{machine['pending_id']}/verification", headers=auth).json()
    assert seen["verification"] == machine["verification"] and len(machine["verification"]) == 6


def test_so_a_conta_dona_do_codigo_ve_a_verificacao_e_confirma(client):
    a = signup(client, "a@exemplo.com")
    b = signup(client, "b@exemplo.com")
    code = client.post("/v1/pair/codes", headers=a).json()["code"]
    pid = client.post("/v1/pair/redeem", json={"code": code, "public_key": "pub-1", "name": "n"}).json()["pending_id"]
    assert client.get(f"/v1/pair/{pid}/verification", headers=b).status_code == 404
    client.post("/v1/pair/machine-confirm", json={"pending_id": pid})
    assert client.post("/v1/pair/confirm", headers=b, json={"pending_id": pid}).status_code == 403
    assert client.get("/v1/installations", headers=b).json() == []


def test_confirmar_so_um_lado_nao_cria_instalacao(client):
    auth = signup(client, "a@exemplo.com")
    code = client.post("/v1/pair/codes", headers=auth).json()["code"]
    pid = client.post("/v1/pair/redeem", json={"code": code, "public_key": "pub-1", "name": "n"}).json()["pending_id"]
    r = client.post("/v1/pair/confirm", headers=auth, json={"pending_id": pid})
    assert r.status_code == 202
    assert client.get("/v1/installations", headers=auth).json() == []
    assert client.get(f"/v1/pair/{pid}").json()["state"] == "pending"


def test_codigo_reaproveitado_recusado(client):
    auth = signup(client, "a@exemplo.com")
    code = client.post("/v1/pair/codes", headers=auth).json()["code"]
    assert client.post("/v1/pair/redeem", json={"code": code, "public_key": "p1", "name": "n"}).status_code == 200
    assert client.post("/v1/pair/redeem", json={"code": code, "public_key": "p2", "name": "n"}).status_code == 400


def test_codigo_expirado_recusado(client, clock):
    auth = signup(client, "a@exemplo.com")
    code = client.post("/v1/pair/codes", headers=auth).json()["code"]
    clock.t += 301
    assert client.post("/v1/pair/redeem", json={"code": code, "public_key": "p1", "name": "n"}).status_code == 400


def test_adivinhar_codigo_bloqueia_a_origem(client):
    auth = signup(client, "a@exemplo.com")
    code = client.post("/v1/pair/codes", headers=auth).json()["code"]
    for _ in range(5):
        assert (
            client.post("/v1/pair/redeem", json={"code": "AAAAAAAA", "public_key": "x", "name": "n"}).status_code == 400
        )
    r = client.post("/v1/pair/redeem", json={"code": code, "public_key": "x", "name": "n"})
    assert r.status_code == 429


def test_listar_so_as_proprias_instalacoes(client):
    a = signup(client, "a@exemplo.com")
    b = signup(client, "b@exemplo.com")
    pair(client, a, "pub-a", "do-a")
    pair(client, b, "pub-b", "do-b")
    assert [i["name"] for i in client.get("/v1/installations", headers=a).json()] == ["do-a"]
    assert [i["name"] for i in client.get("/v1/installations", headers=b).json()] == ["do-b"]


def test_revogar_a_propria_e_a_alheia_recusada(client):
    a = signup(client, "a@exemplo.com")
    b = signup(client, "b@exemplo.com")
    _, ia = pair(client, a, "pub-a", "do-a")
    assert client.delete(f"/v1/installations/{ia['installation_id']}", headers=b).status_code == 404
    assert len(client.get("/v1/installations", headers=a).json()) == 1
    assert client.delete(f"/v1/installations/{ia['installation_id']}", headers=a).status_code == 204
    assert client.get("/v1/installations", headers=a).json() == []


def test_limite_de_2_instalacoes_por_conta(client):
    auth = signup(client, "a@exemplo.com")
    pair(client, auth, "p1", "um")
    pair(client, auth, "p2", "dois")
    code = client.post("/v1/pair/codes", headers=auth).json()["code"]
    pid = client.post("/v1/pair/redeem", json={"code": code, "public_key": "p3", "name": "tres"}).json()["pending_id"]
    client.post("/v1/pair/machine-confirm", json={"pending_id": pid})
    r = client.post("/v1/pair/confirm", headers=auth, json={"pending_id": pid})
    assert r.status_code == 409 and r.json()["detail"] == "quota_installations"
    assert len(client.get("/v1/installations", headers=auth).json()) == 2


def test_logout_invalida_o_token(client):
    auth = signup(client, "a@exemplo.com")
    assert client.post("/v1/logout", headers=auth).status_code == 204
    assert client.get("/v1/installations", headers=auth).status_code == 401


def test_conta_lista_so_os_pareamentos_pendentes_dela(client):
    a = signup(client, "a@exemplo.com")
    b = signup(client, "b@exemplo.com")
    code = client.post("/v1/pair/codes", headers=a).json()["code"]
    red = client.post("/v1/pair/redeem", json={"code": code, "public_key": "pub-1", "name": "meu-note"}).json()
    lista_a = client.get("/v1/pair/pending", headers=a).json()
    assert lista_a == [{"pending_id": red["pending_id"], "verification": red["verification"], "name": "meu-note"}]
    assert client.get("/v1/pair/pending", headers=b).json() == []
    assert client.get("/v1/pair/pending").status_code == 401
