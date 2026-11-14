"""Limites do WebSocket /v1/connect: aperto de mao por IP, prazo do primeiro envelope e taxa de mensagens (fase A)."""

import pytest
from conftest import Machine, signup
from starlette.websockets import WebSocketDisconnect

from heycode.relay import app as relay_app


def closed_with(ws) -> int:
    with pytest.raises(WebSocketDisconnect) as info:
        ws.receive_json()
    return info.value.code


def test_conexao_calada_e_fechada_depois_do_prazo(make_client):
    client = make_client(ws_auth_timeout=0.05)
    with client.websocket_connect("/v1/connect") as ws:
        assert closed_with(ws) == relay_app.CLOSE_UNAUTHORIZED


def test_aperto_de_mao_tem_limite_por_ip(client, clock):
    for _ in range(20):
        with client.websocket_connect("/v1/connect") as ws:
            ws.send_json({"lixo": True})
            assert closed_with(ws) == relay_app.CLOSE_UNAUTHORIZED
    with client.websocket_connect("/v1/connect") as ws:
        assert closed_with(ws) == relay_app.CLOSE_TOO_MANY
    clock.t += 61
    with client.websocket_connect("/v1/connect") as ws:
        ws.send_json({"lixo": True})
        assert closed_with(ws) == relay_app.CLOSE_UNAUTHORIZED


def test_ip_banido_nao_abre_conexao_e_envelope_invalido_nao_bane(make_client, clock):
    client = make_client(ip_limit=1)
    for _ in range(3):
        clock.t += 61
        for _ in range(7):
            with client.websocket_connect("/v1/connect") as ws:
                ws.send_json({"lixo": True})
                closed_with(ws)
    clock.t += 61
    assert client.get("/v1/installations").status_code == 401  # 21 envelopes invalidos nao baniram o IP
    for _ in range(21):
        client.get("/v1/installations")
    with client.websocket_connect("/v1/connect") as ws:
        assert closed_with(ws) == relay_app.CLOSE_TOO_MANY


def test_teto_de_conexoes_ainda_nao_autenticadas(client, monkeypatch):
    monkeypatch.setattr(relay_app, "MAX_WAITING_SOCKETS", 1)
    with client.websocket_connect("/v1/connect") as first:
        with client.websocket_connect("/v1/connect") as second:
            assert closed_with(second) == relay_app.CLOSE_TOO_MANY
        first.send_json({"lixo": True})
        assert closed_with(first) == relay_app.CLOSE_UNAUTHORIZED
    with client.websocket_connect("/v1/connect") as again:  # a vaga voltou
        again.send_json({"lixo": True})
        assert closed_with(again) == relay_app.CLOSE_UNAUTHORIZED


def test_instalacao_que_inunda_de_mensagens_e_desconectada(client, clock, tmp_path):
    machine = Machine(client, signup(client, "ana@exemplo.com"), tmp_path, clock)
    with client.websocket_connect("/v1/connect") as ws:
        ws.send_json(machine.envelope())
        assert ws.receive_json()["type"] == "status"
        for _ in range(240):
            ws.send_json(machine.envelope())
        ws.send_json(machine.envelope())
        assert closed_with(ws) == relay_app.CLOSE_TOO_MANY
