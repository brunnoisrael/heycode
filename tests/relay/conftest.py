import pytest
from fastapi.testclient import TestClient

from heycode.identity.keys import generate_keypair, load_private_key
from heycode.protocol.outbound import build_envelope
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
def make_client(clock):
    """Um TestClient em contexto: HTTP e WebSocket dividem o mesmo laco de eventos, como no servidor real."""
    opened = []

    def make(**kw):
        c = TestClient(create_app(SqliteRepository(":memory:"), clock, **kw))
        c.__enter__()
        opened.append(c)
        return c

    yield make
    for c in opened:
        c.__exit__(None, None, None)


@pytest.fixture
def client(make_client):
    return make_client()


def signup(client, email):
    assert client.post("/v1/register", json={"email": email, "password": "senha-bem-longa"}).status_code == 201
    r = client.post("/v1/login", json={"email": email, "password": "senha-bem-longa"})
    assert r.status_code == 200
    return {"Authorization": "Bearer " + r.json()["token"]}


class Machine:
    """Uma instalacao pareada, com a chave privada para assinar envelopes."""

    def __init__(self, client, auth, tmp_path, clock, name="notebook"):
        self.client, self.clock = client, clock
        pub = generate_keypair(tmp_path)
        self.key = load_private_key(tmp_path)
        code = client.post("/v1/pair/codes", headers=auth).json()["code"]
        pid = client.post("/v1/pair/redeem", json={"code": code, "public_key": pub, "name": name}).json()["pending_id"]
        client.post("/v1/pair/machine-confirm", json={"pending_id": pid})
        self.id = client.post("/v1/pair/confirm", headers=auth, json={"pending_id": pid}).json()["installation_id"]

    def envelope(self, type_="status", payload=None, **over):
        env = build_envelope(
            type_, payload or {"state": "idle"}, installation_id=self.id, private_key=self.key, now=self.clock()
        )
        env.update(over)
        return env
