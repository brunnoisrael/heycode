import io
import json
import os
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from heycode import hook
from heycode.cli import main

# ---------------------------------------------------------------- serve


@pytest.fixture
def fake_uvicorn(monkeypatch):
    calls = []
    monkeypatch.setattr("uvicorn.run", lambda *a, **kw: calls.append((a, kw)))
    return calls


def test_serve_carrega_config_sem_sobrescrever_ambiente(tmp_path, monkeypatch, fake_uvicorn):
    home = tmp_path / "h"
    home.mkdir()
    (home / "config.env").write_text("BRIDGE_SECRET=do-arquivo\nBRIDGE_PIN=1111\n", encoding="utf-8")
    monkeypatch.setenv("HEYCODE_HOME", str(home))
    monkeypatch.setenv("BRIDGE_SECRET", "tmp")  # registra o desfazer: apply_env escreve em os.environ
    monkeypatch.delenv("BRIDGE_SECRET")
    monkeypatch.setenv("BRIDGE_PIN", "9999")
    assert main(["serve", "--port", "18765"]) == 0
    assert os.environ["BRIDGE_SECRET"] == "do-arquivo" and os.environ["BRIDGE_PIN"] == "9999"
    (args, kwargs) = fake_uvicorn[0]
    assert args == ("heycode.app:app",) and kwargs["host"] == "127.0.0.1" and kwargs["port"] == 18765


def test_serve_porta_padrao_e_8765():
    from heycode.cli import build_parser

    args = build_parser().parse_args(["serve"])
    assert args.port == 8765 and args.host == "127.0.0.1"


def test_serve_porta_ocupada_da_mensagem_clara(tmp_path, monkeypatch, fake_uvicorn, capsys):
    monkeypatch.setenv("HEYCODE_HOME", str(tmp_path / "h"))
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        s.listen()
        port = s.getsockname()[1]
        assert main(["serve", "--port", str(port)]) == 1
    assert "porta" in capsys.readouterr().err.lower() and fake_uvicorn == []


# ----------------------------------------------------------------- hook


class Fake:
    def __init__(self, instruction=None, decision=None):
        self.calls = []
        outer = self

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.calls.append((self.path, body, self.headers.get("x-secret")))
                res = {"ok": True}
                if self.path == "/instruction/next":
                    res = {"instruction": instruction}
                elif self.path == "/approval":
                    res = {"decision": decision}
                data = json.dumps(res).encode()
                self.send_response(200)
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


@pytest.fixture
def fake(monkeypatch):
    f = Fake()
    monkeypatch.setenv("BRIDGE_URL", f.url)
    monkeypatch.setenv("BRIDGE_SECRET", "s3")
    yield f
    f.close()


def feed(payload):
    return io.BytesIO(json.dumps(payload).encode("utf-8"))


def test_hook_envia_evento_com_segredo_e_agente(fake):
    assert hook.run(["--agent", "codex"], feed({"hook_event_name": "Notification"})) == 0
    path, body, secret = fake.calls[0]
    assert path == "/event" and body["agent"] == "codex" and secret == "s3"


def test_hook_agente_padrao_e_claude(fake):
    hook.run([], feed({"hook_event_name": "Notification"}))
    assert fake.calls[0][1]["agent"] == "claude"


@pytest.mark.parametrize("decision,expected", [("allow", "allow"), ("deny", "deny")])
def test_hook_approve_imprime_a_decisao(monkeypatch, capsys, decision, expected):
    f = Fake(decision=decision)
    monkeypatch.setenv("BRIDGE_URL", f.url)
    try:
        assert hook.run(["approve"], feed({"hook_event_name": "PermissionRequest"})) == 0
    finally:
        f.close()
    out = json.loads(capsys.readouterr().out)
    assert out["hookSpecificOutput"]["decision"]["behavior"] == expected
    assert ("message" in out["hookSpecificOutput"]["decision"]) == (expected == "deny")


def test_hook_approve_sem_decisao_nao_imprime_nada(monkeypatch, capsys):
    f = Fake(decision=None)
    monkeypatch.setenv("BRIDGE_URL", f.url)
    try:
        assert hook.run(["approve"], feed({})) == 0
    finally:
        f.close()
    assert capsys.readouterr().out == ""


def test_hook_stop_com_instrucao_bloqueia_com_o_texto(monkeypatch, capsys):
    f = Fake(instruction="rode os testes")
    monkeypatch.setenv("BRIDGE_URL", f.url)
    try:
        hook.run([], feed({"hook_event_name": "Stop", "cwd": "/home/ana/projetos/painel/"}))
    finally:
        f.close()
    assert f.calls[1][0] == "/instruction/next" and f.calls[1][1]["project"] == "painel"
    out = json.loads(capsys.readouterr().out)
    assert out["decision"] == "block" and "rode os testes" in out["reason"]


def test_hook_stop_sem_instrucao_nao_imprime_nada(fake, capsys):
    hook.run([], feed({"hook_event_name": "Stop", "cwd": "/x/y"}))
    assert capsys.readouterr().out == ""


def test_hook_com_ponte_fora_do_ar_sai_com_0_em_menos_de_2s(monkeypatch):
    monkeypatch.setenv("BRIDGE_URL", "http://127.0.0.1:1")
    start = time.monotonic()
    assert hook.run([], feed({"hook_event_name": "Notification"})) == 0
    assert time.monotonic() - start < 2


def test_bridge_is_up_com_url_invalida_ou_fechada():
    assert hook.bridge_is_up("http://127.0.0.1:1") is False
    assert hook.bridge_is_up("nao-e-url") is False


def test_bridge_is_up_com_servidor_no_ar(fake):
    assert hook.bridge_is_up(fake.url) is True


def test_hook_com_entrada_invalida_sai_com_0(fake):
    assert hook.run([], io.BytesIO(b"isto nao e json")) == 0


def test_cli_hook_encaminha_os_argumentos(fake, monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(feed({"hook_event_name": "Notification"})))
    assert main(["hook", "--agent", "aider"]) == 0
    assert fake.calls[0][1]["agent"] == "aider"


def test_hook_nao_importa_fastapi():
    code = "import sys; from heycode.cli import main; main(['hook']); print('fastapi' in sys.modules)"
    r = subprocess.run(
        [sys.executable, "-c", code],
        input=b"{}",
        capture_output=True,
        env=dict(os.environ, BRIDGE_URL="http://127.0.0.1:1"),
    )
    assert r.stdout.decode().strip().endswith("False")
