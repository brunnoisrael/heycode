import threading

import pytest
from conftest import Machine, signup
from starlette.websockets import WebSocketDisconnect

from heycode.identity.signing import sign


@pytest.fixture
def setup(client, tmp_path, clock):
    auth = signup(client, "a@exemplo.com")
    return client, auth, Machine(client, auth, tmp_path, clock)


def connect(client, machine, **over):
    ws = client.websocket_connect("/v1/connect")
    s = ws.__enter__()
    s.send_json(machine.envelope(**over))
    return ws, s


def expect_rejected(client, env):
    with client.websocket_connect("/v1/connect") as s:
        s.send_json(env)
        expect_closed(s)


def expect_closed(s):
    with pytest.raises(WebSocketDisconnect):
        s.receive_json()


def test_maquina_conecta_com_envelope_assinado(setup):
    client, auth, m = setup
    ws, s = connect(client, m)
    try:
        assert s.receive_json()["type"] == "status"  # ack
    finally:
        ws.__exit__(None, None, None)


def test_assinatura_invalida_recusada(setup):
    client, auth, m = setup
    env = m.envelope()
    env["payload"]["state"] = "running"  # adulterado depois de assinar
    expect_rejected(client, env)


def test_replay_do_handshake_recusado(setup):
    client, auth, m = setup
    env = m.envelope()
    with client.websocket_connect("/v1/connect") as s1:
        s1.send_json(env)
        s1.receive_json()
        expect_rejected(client, env)  # o mesmo envelope, de novo


def test_instalacao_revogada_nao_conecta(setup):
    client, auth, m = setup
    assert client.delete(f"/v1/installations/{m.id}", headers=auth).status_code == 204
    expect_rejected(client, m.envelope())


def test_relogio_dessincronizado_recusado(setup):
    client, auth, m = setup
    env = m.envelope(ts=m.clock() - 500)
    env["sig"] = sign({k: v for k, v in env.items() if k != "sig"}, m.key)
    expect_rejected(client, env)


def test_instalacao_inexistente_recusada(setup):
    client, auth, m = setup
    expect_rejected(client, m.envelope(installation_id="nao-existe"))


def test_maquina_offline_responde_offline_na_hora(setup):
    client, auth, m = setup
    r = client.post("/v1/skill/request", headers=auth, json={"text": "oi", "destination": "p"})
    assert r.status_code == 200 and r.json() == {"state": "offline"}


def test_sem_resposta_no_prazo_devolve_pending_e_resultado_tardio_fica_disponivel(make_client, tmp_path, clock):
    client = make_client(sync_timeout=0.2)
    auth = signup(client, "a@exemplo.com")
    m = Machine(client, auth, tmp_path, clock)
    ws, s = connect(client, m)
    try:
        s.receive_json()
        r = client.post("/v1/skill/request", headers=auth, json={"text": "faca", "destination": "proj"})
        assert r.json()["state"] == "pending"
        rid = r.json()["request_id"]
        req = s.receive_json()
        assert req["type"] == "instruction" and req["payload"]["text"] == "faca" and req["id"] == rid
        assert client.get(f"/v1/skill/result/{rid}", headers=auth).json() == {"state": "pending"}
        s.send_json(m.envelope("run-result", {"run_id": "1", "state": "done", "summary": "feito", "in_reply_to": rid}))
        for _ in range(50):
            got = client.get(f"/v1/skill/result/{rid}", headers=auth).json()
            if got["state"] == "done":
                break
        assert got["state"] == "done" and got["result"]["summary"] == "feito"
    finally:
        ws.__exit__(None, None, None)


def test_resposta_dentro_do_prazo_volta_na_mesma_chamada(make_client, tmp_path, clock):
    client = make_client(sync_timeout=3)
    auth = signup(client, "a@exemplo.com")
    m = Machine(client, auth, tmp_path, clock)
    ws, s = connect(client, m)
    try:
        s.receive_json()
        out = {}

        def ask():
            out["r"] = client.post("/v1/skill/request", headers=auth, json={"text": "faca", "destination": "p"})

        t = threading.Thread(target=ask)
        t.start()
        req = s.receive_json()
        s.send_json(
            m.envelope("run-result", {"run_id": "1", "state": "done", "summary": "ok", "in_reply_to": req["id"]})
        )
        t.join(5)
        assert out["r"].json()["state"] == "done" and out["r"].json()["result"]["summary"] == "ok"
    finally:
        ws.__exit__(None, None, None)


def test_segunda_conexao_substitui_a_primeira(make_client, tmp_path, clock):
    client = make_client(sync_timeout=0.2)
    auth = signup(client, "a@exemplo.com")
    m = Machine(client, auth, tmp_path, clock)
    ws1, s1 = connect(client, m)
    s1.receive_json()
    ws2, s2 = connect(client, m)
    s2.receive_json()
    expect_closed(s1)
    r = client.post("/v1/skill/request", headers=auth, json={"text": "x", "destination": "p"})
    assert r.json()["state"] == "pending"
    assert s2.receive_json()["type"] == "instruction"
    ws2.__exit__(None, None, None)
    ws1.__exit__(None, None, None)


def test_revogar_derruba_a_conexao_ativa(setup):
    client, auth, m = setup
    ws, s = connect(client, m)
    try:
        s.receive_json()
        client.delete(f"/v1/installations/{m.id}", headers=auth)
        expect_closed(s)
    finally:
        ws.__exit__(None, None, None)
