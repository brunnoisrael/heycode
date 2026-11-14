import pytest
from conftest import Machine, signup


def listed(client, auth):
    return client.get("/v1/installations", headers=auth).json()


def test_listagem_traz_online_e_padrao(make_client, tmp_path_factory, clock):
    client = make_client()
    auth = signup(client, "a@exemplo.com")
    m1 = Machine(client, auth, tmp_path_factory.mktemp("1"), clock, "um")
    m2 = Machine(client, auth, tmp_path_factory.mktemp("2"), clock, "dois")
    client.put("/v1/default-installation", headers=auth, json={"installation_id": m2.id})
    with client.websocket_connect("/v1/connect") as ws:
        ws.send_json(m1.envelope())
        ws.receive_json()
        by_id = {i["id"]: i for i in listed(client, auth)}
    assert by_id[m1.id]["online"] is True and by_id[m2.id]["online"] is False
    assert by_id[m2.id]["is_default"] is True and by_id[m1.id]["is_default"] is False


def test_renomear_o_proprio_computador(client, tmp_path, clock):
    auth = signup(client, "a@exemplo.com")
    m = Machine(client, auth, tmp_path, clock, "antigo")
    r = client.patch(f"/v1/installations/{m.id}", headers=auth, json={"name": "  Notebook da sala  "})
    assert r.status_code == 200 and r.json()["name"] == "Notebook da sala"
    assert listed(client, auth)[0]["name"] == "Notebook da sala"
    rows = client.get("/v1/audit", headers=auth).json()
    assert (rows[0]["kind"], rows[0]["label"]) == ("painel:renomear_computador", "Notebook da sala")


@pytest.mark.parametrize("name", ["", "   ", "x" * 65])
def test_nome_invalido_e_recusado(client, tmp_path, clock, name):
    auth = signup(client, "a@exemplo.com")
    m = Machine(client, auth, tmp_path, clock)
    assert client.patch(f"/v1/installations/{m.id}", headers=auth, json={"name": name}).status_code == 422


def test_nao_renomeia_computador_de_outra_conta(client, tmp_path, clock):
    a = signup(client, "a@exemplo.com")
    b = signup(client, "b@exemplo.com")
    m = Machine(client, a, tmp_path, clock, "do-a")
    assert client.patch(f"/v1/installations/{m.id}", headers=b, json={"name": "invadido"}).status_code == 404
    assert listed(client, a)[0]["name"] == "do-a"


def test_nao_renomeia_computador_revogado(client, tmp_path, clock):
    auth = signup(client, "a@exemplo.com")
    m = Machine(client, auth, tmp_path, clock)
    client.delete(f"/v1/installations/{m.id}", headers=auth)
    assert client.patch(f"/v1/installations/{m.id}", headers=auth, json={"name": "x"}).status_code == 404
