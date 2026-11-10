import importlib
import os
import sys

import pytest

BRIDGE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "bridge")


@pytest.fixture
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setenv("BRIDGE_SECRET", "s")
    monkeypatch.setenv("BRIDGE_DB", str(tmp_path / "bridge.db"))
    monkeypatch.setenv("APPROVAL_WAIT", "1")
    monkeypatch.setenv("BRIDGE_PIN", "1234")
    monkeypatch.setenv("NTFY_TOPIC", "")
    monkeypatch.syspath_prepend(os.path.abspath(BRIDGE_DIR))
    if "server" in sys.modules:
        server = importlib.reload(sys.modules["server"])
    else:
        server = importlib.import_module("server")
    with TestClient(server.app, headers={"x-secret": "s"}) as c:
        c.server = server
        yield c
    server.store.close()
