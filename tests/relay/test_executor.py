import asyncio
import json

import httpx
import pytest

from heycode.relay_executor import ALLOWED, BridgeExecutor


class Recorder:
    def __init__(self, status=200, body=None):
        self.requests = []
        self.status = status
        self.body = {"speech": "ok"} if body is None else body

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(self.status, json=self.body)


def make(rec, auto_allowed=False, secret="segredo-de-controle"):
    transport = httpx.MockTransport(rec.handler)
    return BridgeExecutor("http://127.0.0.1:8765", secret, auto_allowed=lambda: auto_allowed, transport=transport)


def run(ex, method, path, body=None):
    payload = {"method": method, "path": path}
    if body is not None:
        payload["body"] = body
    return asyncio.run(ex(payload))


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/status"),
        ("GET", "/pending"),
        ("GET", "/result"),
        ("GET", "/voice/audit?limit=10"),
        ("GET", "/voice/projects?offset=0"),
        ("GET", "/voice/projects/status?project=meu%20app"),
        ("GET", "/voice/projects/resolve?name=meu%20app"),
        ("POST", "/decide"),
        ("POST", "/mode"),
        ("POST", "/dictation"),
        ("POST", "/answer/preview"),
        ("POST", "/answer/confirm"),
        ("POST", "/projects"),
        ("POST", "/confirm"),
        ("POST", "/cancel"),
        ("POST", "/runs/latest/cancel"),
    ],
)
def test_rotas_da_lista_passam_com_o_segredo_de_controle(method, path):
    rec = Recorder()
    out = run(make(rec), method, path, {"x": 1} if method == "POST" else None)
    assert out == {"status": 200, "body": {"speech": "ok"}}
    sent = rec.requests[0]
    assert sent.method == method and sent.url.host == "127.0.0.1"
    assert sent.headers["x-secret"] == "segredo-de-controle"


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/mcp"),  # fora da lista
        ("POST", "/event"),  # rota dos agentes
        ("POST", "/instruction/next"),
        ("GET", "/runs/latest"),  # existe na ponte, mas o Lambda nao usa
        ("POST", "/runs"),
        ("GET", "/health"),
        ("POST", "/status"),  # metodo trocado
        ("GET", "/decide"),
        ("GET", "/status/../mcp"),  # sai do caminho
        ("GET", "//evil.example/status"),
        ("GET", "/status#x"),
        ("GET", "/Status"),
        ("GET", "/status/"),
    ],
)
def test_qualquer_rota_fora_da_lista_e_recusada_sem_tocar_a_ponte(method, path):
    rec = Recorder()
    out = run(make(rec), method, path)
    assert out["status"] == 403 and out["body"]["error"] == "not_allowed"
    assert rec.requests == []


def test_consulta_com_chave_nao_permitida_recusada():
    rec = Recorder()
    out = run(make(rec), "GET", "/voice/projects?offset=0&admin=1")
    assert out["status"] == 403 and rec.requests == []
    out = run(make(rec), "GET", "/status?x=1")  # /status nao aceita consulta nenhuma
    assert out["status"] == 403 and rec.requests == []


def test_valor_de_consulta_gigante_recusado():
    rec = Recorder()
    out = run(make(rec), "GET", "/voice/projects/resolve?name=" + "a" * 500)
    assert out["status"] == 403 and rec.requests == []


def test_get_com_corpo_recusado():
    rec = Recorder()
    out = run(make(rec), "GET", "/status", {"x": 1})
    assert out["status"] == 403 and rec.requests == []


def test_auto_so_passa_se_ligado_no_computador():
    rec = Recorder()
    out = run(make(rec, auto_allowed=False), "POST", "/mode", {"mode": "auto"})
    assert out["status"] == 403 and out["body"]["error"] == "auto_not_allowed"
    assert "relay-auto" in out["body"]["speech"] and rec.requests == []
    out = run(make(rec, auto_allowed=True), "POST", "/mode", {"mode": "auto"})
    assert out["status"] == 200 and len(rec.requests) == 1


@pytest.mark.parametrize("mode", ["manual", "decisoes"])
def test_outros_modos_passam_sempre(mode):
    rec = Recorder()
    assert run(make(rec), "POST", "/mode", {"mode": mode})["status"] == 200


def test_auto_com_variacao_de_escrita_tambem_e_barrado():
    rec = Recorder()
    for mode in ("AUTO", " auto", "Auto"):
        assert run(make(rec), "POST", "/mode", {"mode": mode})["status"] == 403
    assert rec.requests == []


def test_alteracao_do_auto_allowed_vale_na_hora():
    state = {"on": False}
    rec = Recorder()
    ex = BridgeExecutor(
        "http://127.0.0.1:8765", "s", auto_allowed=lambda: state["on"], transport=httpx.MockTransport(rec.handler)
    )
    assert run(ex, "POST", "/mode", {"mode": "auto"})["status"] == 403
    state["on"] = True
    assert run(ex, "POST", "/mode", {"mode": "auto"})["status"] == 200


def test_ponte_fora_do_ar_vira_502_sem_levantar():
    def boom(request):
        raise httpx.ConnectError("recusado")

    ex = BridgeExecutor("http://127.0.0.1:8765", "s", auto_allowed=lambda: False, transport=httpx.MockTransport(boom))
    out = run(ex, "GET", "/status")
    assert out == {"status": 502, "body": {"error": "bridge_unreachable"}}


def test_resposta_da_ponte_que_nao_e_objeto_e_embrulhada():
    rec = Recorder(body=["a", "b"])
    assert run(make(rec), "GET", "/status")["body"] == {"value": ["a", "b"]}


def test_erro_http_da_ponte_e_repassado_com_o_corpo():
    rec = Recorder(status=401, body={"detail": "no"})
    assert run(make(rec), "GET", "/status") == {"status": 401, "body": {"detail": "no"}}


def test_segredo_nunca_aparece_no_resultado():
    rec = Recorder(status=500, body={"detail": "erro"})
    out = run(make(rec, secret="s3gredo-unico-xyz"), "GET", "/status")
    assert "s3gredo-unico-xyz" not in json.dumps(out)


def test_lista_permitida_e_exatamente_a_do_lambda():
    assert ALLOWED == {
        ("GET", "/status"): set(),
        ("GET", "/pending"): set(),
        ("GET", "/result"): set(),
        ("GET", "/voice/audit"): {"limit"},
        ("GET", "/voice/projects"): {"offset"},
        ("GET", "/voice/projects/status"): {"project"},
        ("GET", "/voice/projects/resolve"): {"name"},
        ("POST", "/decide"): set(),
        ("POST", "/mode"): set(),
        ("POST", "/dictation"): set(),
        ("POST", "/answer/preview"): set(),
        ("POST", "/answer/confirm"): set(),
        ("POST", "/projects"): set(),
        ("POST", "/confirm"): set(),
        ("POST", "/cancel"): set(),
        ("POST", "/runs/latest/cancel"): set(),
    }
