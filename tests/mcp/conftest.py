import importlib
import os
import sys

import pytest

AGENT_SECRET = "agente-" + "a" * 40
CONTROL_SECRET = "controle-" + "c" * 40


@pytest.fixture
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setenv("BRIDGE_SECRET", AGENT_SECRET)
    monkeypatch.setenv("BRIDGE_CONTROL_SECRET", CONTROL_SECRET)
    monkeypatch.setenv("BRIDGE_DB", str(tmp_path / "bridge.db"))
    monkeypatch.setenv("APPROVAL_WAIT", "1")
    monkeypatch.setenv("BRIDGE_PIN", "1234")
    monkeypatch.setenv("NTFY_TOPIC", "")
    if "heycode.app" in sys.modules:
        server = importlib.reload(sys.modules["heycode.app"])
    else:
        server = importlib.import_module("heycode.app")
    with TestClient(server.app, headers={"x-secret": CONTROL_SECRET}) as c:
        c.server = server
        c.agent_h = {"x-secret": AGENT_SECRET}      # hooks e MCP
        c.control_h = {"x-secret": CONTROL_SECRET}  # Lambda (padrao do cliente)
        yield c
    server.store.close()
