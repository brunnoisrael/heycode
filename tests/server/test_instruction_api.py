def test_sem_auth_401(client):
    r = client.post("/instruction", json={"text": "x"}, headers={"x-secret": "errado"})
    assert r.status_code == 401
    r = client.post("/instruction/next", json={"agent": "claude"}, headers={"x-secret": "errado"})
    assert r.status_code == 401


def test_texto_invalido_422(client):
    assert client.post("/instruction", json={"text": ""}).status_code == 422
    assert client.post("/instruction", json={"text": "a" * 301}).status_code == 422
    assert client.post("/instruction", json={"text": "a" * 300}).status_code == 200


def test_next_entrega_e_esvazia(client):
    i = client.post("/instruction", json={"text": "rode os testes"}).json()["id"]
    assert isinstance(i, int)
    assert client.post("/instruction/next", json={"agent": "claude"}).json() == {"instruction": "rode os testes"}
    assert client.post("/instruction/next", json={"agent": "claude"}).json() == {"instruction": None}


def test_projeto_nao_vaza(client):
    client.post("/instruction", json={"text": "x", "project": "a"})
    assert client.post("/instruction/next", json={"agent": "claude", "project": "b"}).json() == {"instruction": None}
    assert client.post("/instruction/next", json={"agent": "claude", "project": "a"}).json() == {"instruction": "x"}
