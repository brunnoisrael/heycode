import asyncio
import json

import pytest

from heycode.identity.keys import generate_keypair, load_private_key
from heycode.identity.signing import verify
from heycode.relay_client import RelayClient, backoff_delay


def test_backoff_exponencial_de_1s_a_60s_com_jitter():
    sem_jitter = [backoff_delay(n, rand=lambda: 0.5) for n in range(10)]
    assert sem_jitter[0] == pytest.approx(1.0)
    assert sem_jitter[1] == pytest.approx(2.0)
    assert sem_jitter[2] == pytest.approx(4.0)
    assert max(sem_jitter) <= 60.0 and sem_jitter[-1] == 60.0
    for n in range(12):
        for r in (0.0, 0.5, 1.0):
            assert 1.0 <= backoff_delay(n, rand=lambda r=r: r) <= 60.0


class FakeWS:
    """Conexao falsa: entrega `incoming` e guarda o que o cliente envia."""

    def __init__(self, incoming):
        self.incoming = list(incoming)
        self.sent = []

    async def send(self, data):
        self.sent.append(json.loads(data))

    async def recv(self):
        if not self.incoming:
            raise ConnectionError("fim")
        item = self.incoming.pop(0)
        if isinstance(item, Exception):
            raise item
        return json.dumps(item)

    async def close(self):
        pass


class FakeConnect:
    def __init__(self, plans):
        self.plans = list(plans)  # cada item: excecao (falha ao conectar) ou FakeWS
        self.calls = 0

    def __call__(self, url):
        self.calls += 1
        plan = self.plans.pop(0)

        class CM:
            async def __aenter__(self):
                if isinstance(plan, Exception):
                    raise plan
                return plan

            async def __aexit__(self, *a):
                return False

        return CM()


ACK = {
    "v": 1,
    "id": "x",
    "ts": 1.0,
    "installation_id": "inst",
    "type": "status",
    "payload": {"state": "idle"},
    "sig": "",
}


def instr(text="faca", rid="018f0000-0000-7000-8000-000000000009"):
    return {
        "v": 1,
        "id": rid,
        "ts": 1.0,
        "installation_id": "inst",
        "type": "instruction",
        "payload": {"text": text, "destination": "proj"},
        "sig": "",
    }


@pytest.fixture
def keys(tmp_path):
    pub = generate_keypair(tmp_path)
    return pub, load_private_key(tmp_path)


def make_client(keys, connect, handler, sleeps, stop_after=None):
    pub, priv = keys
    client = RelayClient(
        "wss://relay.exemplo/v1/connect",
        "inst",
        priv,
        handler,
        clock=lambda: 1000.0,
        connect=connect,
        sleep=None,
    )

    async def fake_sleep(d):
        sleeps.append(d)
        if stop_after is not None and len(sleeps) >= stop_after:
            client.stop()

    client._sleep = fake_sleep
    return client


def test_handshake_assinado_e_resposta_correlacionada(keys):
    pub, _ = keys
    ws = FakeWS([ACK, instr("faca"), ConnectionError("queda")])
    seen = []

    async def handler(payload):
        seen.append(payload)
        return {"run_id": "1", "state": "done", "summary": "feito"}

    client = make_client(keys, FakeConnect([ws]), handler, [], stop_after=1)
    asyncio.run(client.run_forever())
    handshake, reply = ws.sent[0], ws.sent[1]
    verify(handshake, pub, 1000.0)
    assert handshake["type"] == "status" and handshake["installation_id"] == "inst"
    verify(reply, pub, 1000.0)
    assert reply["type"] == "run-result"
    assert reply["payload"]["in_reply_to"] == "018f0000-0000-7000-8000-000000000009"
    assert reply["payload"]["summary"] == "feito"
    assert seen[0]["text"] == "faca"


def test_reconecta_apos_queda_com_backoff_e_zera_depois_de_conectar(keys):
    sleeps = []
    plans = [OSError("recusado"), OSError("recusado"), FakeWS([ACK, ConnectionError("queda")]), OSError("de novo")]
    client = make_client(keys, FakeConnect(plans), lambda p: None, sleeps, stop_after=4)
    asyncio.run(client.run_forever())
    assert 1.0 <= sleeps[0] <= 1.2 and 1.6 <= sleeps[1] <= 2.4  # falhas consecutivas: ~1 s, ~2 s (jitter de 20%)
    assert 1.0 <= sleeps[2] <= 1.2  # conectou e caiu: contador zerou
    assert 1.6 <= sleeps[3] <= 2.4  # a falha seguinte recomeca da escada


def test_erro_do_handler_nao_derruba_a_sessao_e_vira_error(keys):
    pub, _ = keys
    ws = FakeWS([ACK, instr("a", "018f0000-0000-7000-8000-00000000000a"), instr("b"), ConnectionError("fim")])
    calls = []

    async def handler(payload):
        calls.append(payload["text"])
        if payload["text"] == "a":
            raise RuntimeError("agente quebrou")
        return {"run_id": "2", "state": "done", "summary": "ok"}

    client = make_client(keys, FakeConnect([ws]), handler, [], stop_after=1)
    asyncio.run(client.run_forever())
    assert calls == ["a", "b"]
    erro, ok = ws.sent[1], ws.sent[2]
    assert erro["type"] == "error" and erro["payload"]["code"] == "handler_failed"
    assert erro["payload"]["in_reply_to"] == "018f0000-0000-7000-8000-00000000000a"
    verify(erro, pub, 1000.0)
    assert ok["type"] == "run-result"


def test_run_forever_nunca_levanta_para_o_agente(keys):
    sleeps = []
    plans = [RuntimeError("estranho"), ValueError("pior")]
    client = make_client(keys, FakeConnect(plans), lambda p: None, sleeps, stop_after=2)
    asyncio.run(client.run_forever())  # nao levanta
    assert len(sleeps) == 2


def test_resposta_do_handler_com_segredo_e_mascarada(keys):
    ws = FakeWS([ACK, instr(), ConnectionError("fim")])
    segredo = "ghp_" + "b" * 36

    async def handler(payload):
        return {"run_id": "1", "state": "done", "summary": f"usei {segredo}"}

    client = make_client(keys, FakeConnect([ws]), handler, [], stop_after=1)
    asyncio.run(client.run_forever())
    assert segredo not in json.dumps(ws.sent)


def test_frame_malformado_do_relay_e_ignorado(keys):
    ws = FakeWS([ACK, {"lixo": True}, instr(), ConnectionError("fim")])
    calls = []

    async def handler(payload):
        calls.append(1)
        return {"run_id": "1", "state": "done", "summary": "ok"}

    client = make_client(keys, FakeConnect([ws]), handler, [], stop_after=1)
    asyncio.run(client.run_forever())
    assert calls == [1]


def call_frame(path="/status", rid="018f0000-0000-7000-8000-00000000000b", method="GET"):
    return {
        "v": 1,
        "id": rid,
        "ts": 1.0,
        "installation_id": "inst",
        "type": "bridge-call",
        "payload": {"method": method, "path": path},
        "sig": "",
    }


def test_bridge_call_e_executado_e_respondido_como_bridge_result(keys):
    pub, _ = keys
    ws = FakeWS([ACK, call_frame(), ConnectionError("fim")])
    seen = []

    async def bridge(payload):
        seen.append(payload)
        return {"status": 200, "body": {"speech": "tudo certo"}}

    async def handler(payload):
        raise AssertionError("instruction nao deveria ser chamado")

    client = make_client(keys, FakeConnect([ws]), handler, [], stop_after=1)
    client._bridge = bridge
    asyncio.run(client.run_forever())
    reply = ws.sent[1]
    verify(reply, pub, 1000.0)
    assert reply["type"] == "bridge-result"
    assert reply["payload"] == {
        "status": 200,
        "body": {"speech": "tudo certo"},
        "in_reply_to": "018f0000-0000-7000-8000-00000000000b",
    }
    assert seen == [{"method": "GET", "path": "/status"}]


def test_erro_no_executor_vira_error_e_a_sessao_continua(keys):
    ws = FakeWS([ACK, call_frame(), call_frame(rid="018f0000-0000-7000-8000-00000000000c"), ConnectionError("fim")])
    calls = []

    async def bridge(payload):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("falha interna")
        return {"status": 200, "body": {}}

    client = make_client(keys, FakeConnect([ws]), lambda p: None, [], stop_after=1)
    client._bridge = bridge
    asyncio.run(client.run_forever())
    assert ws.sent[1]["type"] == "error" and ws.sent[1]["payload"]["code"] == "handler_failed"
    assert ws.sent[2]["type"] == "bridge-result"


def test_sem_executor_configurado_bridge_call_e_ignorado(keys):
    ws = FakeWS([ACK, call_frame(), ConnectionError("fim")])
    client = make_client(keys, FakeConnect([ws]), lambda p: None, [], stop_after=1)
    asyncio.run(client.run_forever())
    assert len(ws.sent) == 1  # so o handshake: nada executado, nada respondido
