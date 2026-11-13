import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

HOOK = os.path.join(os.path.dirname(__file__), "..", "..", "bridge", "hook.py")


class Fake:
    def __init__(self, instruction=None, decision=None):
        self.calls = []
        outer = self

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.calls.append((self.path, body))
                if self.path == "/instruction/next":
                    res = {"instruction": instruction}
                elif self.path == "/approval":
                    res = {"decision": decision}
                else:
                    res = {"ok": True}
                data = json.dumps(res).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *a):
                pass

        self.srv = HTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.srv.server_port}"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def close(self):
        self.srv.shutdown()
        self.srv.server_close()


def run(args, payload, url):
    env = dict(os.environ, BRIDGE_URL=url, BRIDGE_SECRET="s")
    return subprocess.run([sys.executable, HOOK, *args], input=json.dumps(payload),
                          capture_output=True, text=True, env=env, timeout=30)


def test_agent_codex_vai_no_corpo():
    f = Fake()
    try:
        r = run(["--agent", "codex"], {"hook_event_name": "Notification"}, f.url)
    finally:
        f.close()
    assert r.returncode == 0
    assert f.calls[0][0] == "/event"
    assert f.calls[0][1]["agent"] == "codex"


def test_agent_padrao_claude():
    f = Fake()
    try:
        run([], {"hook_event_name": "Notification"}, f.url)
    finally:
        f.close()
    assert f.calls[0][1]["agent"] == "claude"


def test_stop_com_instrucao_bloqueia():
    f = Fake(instruction="rode os testes")
    try:
        r = run([], {"hook_event_name": "Stop", "cwd": "/x/proj"}, f.url)
    finally:
        f.close()
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out == {"decision": "block",
                   "reason": "Instrução do dono, ditada pela Alexa e confirmada por voz: rode os testes"}
    assert r.stdout.isascii()  # sem depender da codificacao do console no Windows
    assert [c[0] for c in f.calls] == ["/event", "/instruction/next"]
    assert f.calls[1][1] == {"agent": "claude", "project": "proj"}  # mesmas chaves do /event (ADR 0018)


def test_stop_sem_instrucao_silencioso():
    f = Fake(instruction=None)
    try:
        r = run([], {"hook_event_name": "Stop"}, f.url)
    finally:
        f.close()
    assert r.returncode == 0 and r.stdout == ""


def test_ponte_fora_do_ar_stop():
    r = run([], {"hook_event_name": "Stop"}, "http://127.0.0.1:1")
    assert r.returncode == 0 and r.stdout == ""


def test_approve_allow_deny_ask():
    for dec, expected in (("allow", {"behavior": "allow"}),
                          ("deny", {"behavior": "deny", "message": "Negado por voz via Alexa."})):
        f = Fake(decision=dec)
        try:
            r = run(["approve"], {"tool_name": "Bash"}, f.url)
        finally:
            f.close()
        out = json.loads(r.stdout)
        assert out["hookSpecificOutput"]["decision"] == expected
        assert out["hookSpecificOutput"]["hookEventName"] == "PermissionRequest"
    f = Fake(decision="ask")
    try:
        r = run(["approve"], {"tool_name": "Bash"}, f.url)
    finally:
        f.close()
    assert r.returncode == 0 and r.stdout == ""


def test_stdin_utf8_chega_integro_ao_servidor():
    f = Fake()
    texto = "adicione validação de formulário"
    texto2 = "ÍNDICE do Ártico"
    payload = {"hook_event_name": "Notification", "message": texto, "extra": texto2}
    env = dict(os.environ, BRIDGE_URL=f.url, BRIDGE_SECRET="s")
    try:
        r = subprocess.run([sys.executable, HOOK], input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                           capture_output=True, env=env, timeout=30)
    finally:
        f.close()
    assert r.returncode == 0
    assert f.calls[0][1]["message"] == texto
    assert f.calls[0][1]["extra"] == texto2


@pytest.mark.skipif(sys.platform != "win32", reason="usa caminho do Windows (barra invertida)")
def test_stop_no_windows_usa_o_nome_da_pasta_como_projeto():
    f = Fake(instruction=None)
    try:
        run([], {"hook_event_name": "Stop", "cwd": "C:\\Users\\dono\\Projetos\\painel\\"}, f.url)
    finally:
        f.close()
    assert f.calls[1] == ("/instruction/next", {"agent": "claude", "project": "painel"})
