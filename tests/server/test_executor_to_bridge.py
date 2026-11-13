"""Executor local (lista fechada) falando com a ponte REAL por ASGI: da chamada do relay ate a execucao do script."""

import asyncio
import json
import sys

import httpx
import pytest

from heycode.relay_executor import BridgeExecutor

CONTROL = "controle-" + "c" * 40


@pytest.fixture
def bridge(tmp_path, monkeypatch, client):
    """`client` ja subiu a ponte; o executor entra por ASGI, com o mesmo segredo de controle."""
    transport = httpx.ASGITransport(app=client.server.app)
    state = {"auto": False}
    ex = BridgeExecutor("http://ponte.local", CONTROL, auto_allowed=lambda: state["auto"], transport=transport)
    return ex, client, state


@pytest.fixture(autouse=True)
def _home(tmp_path, monkeypatch):
    monkeypatch.setenv("HEYCODE_HOME", str(tmp_path))


def call(ex, method, path, body=None):
    payload = {"method": method, "path": path}
    if body is not None:
        payload["body"] = body
    return asyncio.run(ex(payload))


def put(tmp_path, *cmds):
    (tmp_path / "commands.json").write_text(json.dumps({"version": 1, "commands": list(cmds)}), encoding="utf-8")


def test_do_executor_ate_o_script_confirmar_e_pin(tmp_path, bridge):
    ex, client, _ = bridge
    marker = tmp_path / "rodou.txt"
    code = f"open({str(marker)!r}, 'w').write('ok')"
    put(
        tmp_path,
        {"name": "gravar marca", "type": "script", "risk": "confirmar", "argv": [sys.executable, "-c", code]},
        {"name": "gravar pin", "type": "script", "risk": "pin", "argv": [sys.executable, "-c", code]},
    )
    out = call(ex, "POST", "/voice/commands/run", {"spoken": "gravar marca"})
    assert out["status"] == 200 and out["body"]["pending"] == {"risk": "confirmar"} and not marker.exists()
    done = call(ex, "POST", "/voice/commands/confirm", {})
    assert done["body"]["done"] is True and marker.exists()
    marker.unlink()
    client.server.command_runner._last_run.clear()
    call(ex, "POST", "/voice/commands/run", {"spoken": "gravar pin"})
    assert call(ex, "POST", "/voice/commands/confirm", {"pin": "9999"})["body"]["done"] is False and not marker.exists()
    ok = call(ex, "POST", "/voice/commands/confirm", {"pin": "1234"})
    assert ok["body"]["done"] is True and marker.exists()


def test_listar_pelo_executor_nao_vaza_argv(tmp_path, bridge):
    ex, *_ = bridge
    put(
        tmp_path,
        {"name": "ver disco", "type": "script", "risk": "leitura", "argv": [sys.executable, "-c", "print('x')"]},
    )
    out = call(ex, "GET", "/voice/commands")
    assert [c["name"] for c in out["body"]["commands"]] == ["ver disco"]
    assert sys.executable not in json.dumps(out)


def test_o_executor_nao_alcanca_rotas_de_escrita_do_registro(tmp_path, bridge):
    ex, *_ = bridge
    put(
        tmp_path,
        {"name": "ver disco", "type": "script", "risk": "leitura", "argv": [sys.executable, "-c", "print('x')"]},
    )
    for path in ("/voice/commands/enable", "/voice/commands/add", "/voice/commands/remove"):
        assert call(ex, "POST", path, {"name": "ver disco"})["status"] == 403  # nem chega a ponte
    assert call(ex, "POST", "/voice/commands/disable", {"name": "ver disco"})["body"]["ok"] is True
    saved = json.loads((tmp_path / "commands.json").read_text(encoding="utf-8"))
    assert saved["commands"][0]["enabled"] is False
