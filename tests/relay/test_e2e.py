"""Ponta a ponta com servidor real: pareia, conecta e leva um pedido da skill ate o 'agente' local e de volta."""

import asyncio
import socket
import threading
import time

import httpx
import pytest
import uvicorn

from heycode.identity.keys import load_private_key
from heycode.relay.app import create_app
from heycode.relay.repo import SqliteRepository
from heycode.relay_client import (
    PairingError,
    RelayClient,
    check_relay_url,
    load_relay_config,
    pair_with_relay,
    ws_url,
)


@pytest.fixture
def server():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    app = create_app(SqliteRepository(":memory:"), time.time)
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=srv.run, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            if httpx.get(base + "/health", timeout=0.5).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.05)
    yield base
    srv.should_exit = True
    thread.join(5)


def login(base):
    httpx.post(base + "/v1/register", json={"email": "a@exemplo.com", "password": "senha-bem-longa"})
    token = httpx.post(base + "/v1/login", json={"email": "a@exemplo.com", "password": "senha-bem-longa"}).json()[
        "token"
    ]
    return {"Authorization": "Bearer " + token}


def pair_machine(base, auth, home):
    code = httpx.post(base + "/v1/pair/codes", headers=auth).json()["code"]
    shown = []

    def confirm(verification):
        shown.append(verification)
        pend = httpx.get(base + "/v1/pair/pending", headers=auth).json()
        assert [p["verification"] for p in pend] == [verification]  # mesmo codigo nos dois lados
        r = httpx.post(base + "/v1/pair/confirm", headers=auth, json={"pending_id": pend[0]["pending_id"]})
        assert r.status_code == 202  # so a conta confirmou ate aqui
        return True

    iid = pair_with_relay(base, code, "notebook", home, http=httpx, confirm=confirm)
    return iid, shown


def test_pareamento_ponta_a_ponta_grava_a_configuracao(server, tmp_path):
    auth = login(server)
    iid, shown = pair_machine(server, auth, tmp_path)
    assert len(shown[0]) == 6
    cfg = load_relay_config(tmp_path)
    assert cfg == {"relay_url": server, "installation_id": iid}
    assert [i["id"] for i in httpx.get(server + "/v1/installations", headers=auth).json()] == [iid]


def test_tarefa_vai_da_skill_ao_agente_local_e_volta(server, tmp_path):
    auth = login(server)
    iid, _ = pair_machine(server, auth, tmp_path)
    recebido = []

    async def agente(payload):
        recebido.append(payload)
        return {"run_id": "1", "state": "done", "summary": f"fiz: {payload['text']}"}

    client = RelayClient(ws_url(server), iid, load_private_key(tmp_path), agente)
    loop = asyncio.new_event_loop()
    task_holder = {}

    def run():
        asyncio.set_event_loop(loop)
        task_holder["t"] = loop.create_task(client.run_forever())
        try:
            loop.run_until_complete(task_holder["t"])
        except asyncio.CancelledError:
            pass

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    try:
        for _ in range(100):  # espera a maquina conectar
            r = httpx.post(
                server + "/v1/skill/request", headers=auth, json={"text": "rode os testes", "destination": "proj"}
            )
            if r.json()["state"] != "offline":
                break
            time.sleep(0.05)
        assert r.json()["state"] == "done", r.text
        assert r.json()["result"]["summary"] == "fiz: rode os testes"
        assert recebido[0]["destination"] == "proj"
    finally:
        loop.call_soon_threadsafe(task_holder["t"].cancel)
        thread.join(5)


def test_cliente_segue_tentando_quando_o_relay_o_recusa(server, tmp_path):
    """Instalacao revogada: o cliente recebe a recusa e fica tentando de novo, sem levantar para o agente."""
    auth = login(server)
    iid, _ = pair_machine(server, auth, tmp_path)
    tentativas = []

    def conta_conexoes(url):
        from heycode.relay_client import default_connect

        tentativas.append(url)
        return default_connect(url)

    async def agente(payload):
        return {"run_id": "1", "state": "done", "summary": "ok"}

    sleeps = []

    async def sleep_curto(d):
        sleeps.append(d)
        await asyncio.sleep(0.05)

    client = RelayClient(
        ws_url(server), iid, load_private_key(tmp_path), agente, connect=conta_conexoes, sleep=sleep_curto
    )
    loop = asyncio.new_event_loop()
    holder = {}

    def run():
        asyncio.set_event_loop(loop)
        holder["t"] = loop.create_task(client.run_forever())
        try:
            loop.run_until_complete(holder["t"])
        except asyncio.CancelledError:
            pass

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    try:
        for _ in range(100):
            if (
                httpx.post(server + "/v1/skill/request", headers=auth, json={"text": "x", "destination": "p"}).json()[
                    "state"
                ]
                == "done"
            ):
                break
            time.sleep(0.05)
        # revoga e rejeita: o cliente entra em loop de tentativas sem levantar
        httpx.delete(f"{server}/v1/installations/{iid}", headers=auth)
        time.sleep(0.5)
        assert len(tentativas) >= 2 and sleeps  # tentou de novo, com espera entre as tentativas
        assert thread.is_alive()  # o loop do cliente segue vivo
    finally:
        loop.call_soon_threadsafe(holder["t"].cancel)
        thread.join(5)


def test_relay_sem_tls_recusado_fora_do_localhost():
    with pytest.raises(ValueError):
        check_relay_url("ws://relay.exemplo.com/v1/connect")
    check_relay_url("wss://relay.exemplo.com/v1/connect")
    check_relay_url("ws://127.0.0.1:8000/v1/connect")


def test_pareamento_recusa_http_fora_do_localhost(tmp_path):
    with pytest.raises(PairingError):
        pair_with_relay("http://relay.exemplo.com", "ABCD2345", "n", tmp_path, http=None, confirm=lambda v: True)


def test_pareamento_cancelado_nao_grava_configuracao(server, tmp_path):
    auth = login(server)
    code = httpx.post(server + "/v1/pair/codes", headers=auth).json()["code"]
    with pytest.raises(PairingError):
        pair_with_relay(server, code, "n", tmp_path, http=httpx, confirm=lambda v: False)
    assert load_relay_config(tmp_path) is None
    assert httpx.get(server + "/v1/installations", headers=auth).json() == []


def test_pareamento_com_codigo_invalido_explica(server, tmp_path):
    with pytest.raises(PairingError) as e:
        pair_with_relay(server, "AAAAAAAA", "n", tmp_path, http=httpx, confirm=lambda v: True)
    assert "invalid_code" in str(e.value)


def test_segundo_pareamento_exige_force(server, tmp_path):
    auth = login(server)
    pair_machine(server, auth, tmp_path)
    code = httpx.post(server + "/v1/pair/codes", headers=auth).json()["code"]
    with pytest.raises(PairingError) as e:
        pair_with_relay(server, code, "n", tmp_path, http=httpx, confirm=lambda v: True)
    assert "--force" in str(e.value)
