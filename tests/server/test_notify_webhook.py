import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest


class _Hook:
    def __init__(self, status=200):
        self.received = []
        outer = self

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                outer.received.append(json.loads(body))
                self.send_response(status)
                self.end_headers()

            def log_message(self, *a):
                pass

        self.httpd = HTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}/hook"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()


@pytest.fixture
def hook():
    h = _Hook()
    yield h
    h.close()


def _wait_for(pred, timeout=3.0):
    import time
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(0.05)
    return False


def test_webhook_recebe_titulo_e_mensagem(client, hook, monkeypatch):
    monkeypatch.setattr(client.server, "HA_WEBHOOK_URL", hook.url)
    client.server.push("Claude terminou", "Tarefa concluida")
    assert _wait_for(lambda: hook.received)
    assert hook.received[0] == {"title": "Claude terminou", "message": "Tarefa concluida"}


def test_notification_do_agente_dispara_o_webhook(client, hook, monkeypatch):
    monkeypatch.setattr(client.server, "HA_WEBHOOK_URL", hook.url)
    client.post("/event", json={"hook_event_name": "Notification", "session_id": "a",
                                "cwd": "C:/p/app", "message": "preciso de voce"})
    assert _wait_for(lambda: hook.received)
    assert hook.received[0]["message"] == "preciso de voce"


def test_sem_url_nada_e_chamado(client, hook, monkeypatch):
    monkeypatch.setattr(client.server, "HA_WEBHOOK_URL", "")
    client.server.push("t", "m")
    assert not _wait_for(lambda: hook.received, timeout=0.6)


def test_webhook_fora_do_ar_nao_derruba_a_ponte(client, monkeypatch):
    monkeypatch.setattr(client.server, "HA_WEBHOOK_URL", "http://127.0.0.1:9/nada")
    client.server.push("t", "m")
    assert client.get("/health").json() == {"ok": True}


def test_mensagem_do_webhook_sai_mascarada(client, hook, monkeypatch):
    monkeypatch.setattr(client.server, "HA_WEBHOOK_URL", hook.url)
    client.server.push("Aprovar por voz?", "export TOKEN=ghp_abcdefghijklmnopqrstuvwxyz0123456789")
    assert _wait_for(lambda: hook.received)
    assert "ghp_abcdefghijklmnopqrstuvwxyz0123456789" not in hook.received[0]["message"]
