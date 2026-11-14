"""Ponta a ponta com servidor real: Alexa assinada -> relay -> maquina (executor local) -> ponte simulada."""

import asyncio
import datetime as dt
import json
import socket
import threading
import time
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import uvicorn
from test_alexa_verify import NOW, SKILL, URL, Env, sign

from heycode.identity.keys import generate_keypair, load_private_key
from heycode.relay.alexa_verify import AlexaVerifier
from heycode.relay.app import OAuthConfig, create_app
from heycode.relay.repo import SqliteRepository
from heycode.relay_client import RelayClient, ws_url
from heycode.relay_executor import BridgeExecutor

REDIRECT = "https://pitangui.amazon.com/api/skill/link/M2TEST"
CFG = OAuthConfig("alexa-client", "segredo-do-cliente", (REDIRECT,))
DEVICE = "amzn1.ask.device.E2E"


class FakeBridge:
    """Faz as vezes da ponte local (a que o Lambda do dono chama): guarda o que recebeu."""

    def __init__(self):
        self.received = []
        self.state = {"mode": "manual"}

    def handler(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        self.received.append((request.method, request.url.raw_path.decode(), body, request.headers.get("x-secret")))
        path = request.url.path
        if path == "/status":
            return httpx.Response(200, json={"speech": "Nenhum agente em execução."})
        if path == "/voice/commands":
            return httpx.Response(
                200,
                json={
                    "commands": [
                        {
                            "name": "reiniciar app",
                            "aliases": [],
                            "type": "script",
                            "risk": "confirmar",
                            "enabled": True,
                            "description": "reinicia o servico",
                        },
                        {
                            "name": "deploy",
                            "aliases": [],
                            "type": "script",
                            "risk": "pin",
                            "enabled": True,
                            "description": "",
                        },
                    ]
                },
            )
        if path == "/voice/commands/run":
            said = (body or {}).get("spoken", "")
            if "reiniciar" in said:
                return httpx.Response(
                    200,
                    json={
                        "ok": True,
                        "label": "reiniciar app",
                        "pending": {"risk": "confirmar"},
                        "speech": "Vou executar reiniciar app. Confirma?",
                    },
                )
            if "deploy" in said:
                return httpx.Response(
                    200,
                    json={
                        "ok": True,
                        "label": "deploy",
                        "pending": {"risk": "pin"},
                        "speech": "Vou executar deploy. Esse comando exige o seu PIN.",
                    },
                )
            if "disco" in said:
                return httpx.Response(
                    200, json={"ok": True, "label": "ver disco", "speech": "ver disco terminou com sucesso."}
                )
            return httpx.Response(200, json={"ok": False, "speech": "Não achei esse comando."})
        if path == "/voice/commands/confirm":
            if (body or {}).get("pin") not in (None, "1234"):
                return httpx.Response(200, json={"ok": False, "done": False, "speech": "PIN incorreto."})
            return httpx.Response(
                200, json={"ok": True, "done": True, "label": "x", "speech": "Pronto, comando executado."}
            )
        if path == "/voice/commands/cancel":
            return httpx.Response(200, json={"ok": True, "speech": "Cancelado."})
        if path == "/voice/commands/disable":
            return httpx.Response(200, json={"ok": body.get("name") == "reiniciar app", "speech": "desligado"})
        if path == "/dictation":
            return httpx.Response(200, json={"speech": "Vou pedir ao codex. Confirma?", "ok": True})
        if path == "/voice/audit":
            return httpx.Response(
                200,
                json={
                    "approvals": [
                        {
                            "id": 1,
                            "agent": "claude",
                            "project": "api",
                            "tool": "Bash",
                            "command": "ls",
                            "decision": "allow",
                            "t": 1.0,
                        }
                    ],
                    "runs": [],
                    "limit": 20,
                },
            )
        if path == "/pending":
            return httpx.Response(
                200,
                json={"speech": "O claude quer rodar ls.", "approval_id": 7, "kind": "approval", "actionable": True},
            )
        if path == "/decide":
            return httpx.Response(200, json={"speech": "Aprovado.", "ok": True})
        if path == "/mode":
            self.state["mode"] = body.get("mode", self.state["mode"])
            return httpx.Response(
                200, json={"speech": f"Modo {self.state['mode']} ativado.", "mode": self.state["mode"]}
            )
        return httpx.Response(404, json={"detail": "nao existe"})


@pytest.fixture
def world(tmp_path):
    env = Env()
    verifier = AlexaVerifier(SKILL, lambda: NOW, fetch=env.fetch, trust_roots=[env.ca])
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    app = create_app(SqliteRepository(":memory:"), time.time, oauth=CFG, alexa=verifier)
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
    yield base, env, tmp_path
    srv.should_exit = True
    thread.join(5)


class Machine:
    def __init__(self, base, auth, tmp_path, bridge, auto_allowed=False):
        pub = generate_keypair(tmp_path)
        code = httpx.post(base + "/v1/pair/codes", headers=auth).json()["code"]
        pid = httpx.post(base + "/v1/pair/redeem", json={"code": code, "public_key": pub, "name": "notebook"}).json()[
            "pending_id"
        ]
        httpx.post(base + "/v1/pair/machine-confirm", json={"pending_id": pid})
        self.id = httpx.post(base + "/v1/pair/confirm", headers=auth, json={"pending_id": pid}).json()[
            "installation_id"
        ]
        self.auto = {"on": auto_allowed}
        executor = BridgeExecutor(
            "http://127.0.0.1:8765",
            "segredo-de-controle-local",
            auto_allowed=lambda: self.auto["on"],
            transport=httpx.MockTransport(bridge.handler),
        )

        async def instruction(payload):
            return {"run_id": "1", "state": "done", "summary": "ok"}

        self.client = RelayClient(ws_url(base), self.id, load_private_key(tmp_path), instruction, bridge=executor)
        self.loop = asyncio.new_event_loop()
        self.task = None
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        asyncio.set_event_loop(self.loop)
        self.task = self.loop.create_task(self.client.run_forever())
        try:
            self.loop.run_until_complete(self.task)
        except asyncio.CancelledError:
            pass

    def stop(self):
        self.loop.call_soon_threadsafe(self.task.cancel)
        self.thread.join(5)


def link(base):
    httpx.post(base + "/v1/register", json={"email": "a@exemplo.com", "password": "senha-bem-longa"})
    token = httpx.post(base + "/v1/login", json={"email": "a@exemplo.com", "password": "senha-bem-longa"}).json()[
        "token"
    ]
    auth = {"Authorization": "Bearer " + token}
    r = httpx.post(
        base + "/oauth/authorize",
        data={
            "email": "a@exemplo.com",
            "password": "senha-bem-longa",
            "client_id": "alexa-client",
            "redirect_uri": REDIRECT,
            "state": "s",
        },
    )
    code = parse_qs(urlparse(r.headers["location"]).query)["code"][0]
    tok = httpx.post(
        base + "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT,
            "client_id": "alexa-client",
            "client_secret": "segredo-do-cliente",
        },
    ).json()["access_token"]
    return auth, tok


def say(base, env, tok, intent=None, slots=None, attrs=None, rtype=None):
    ts = dt.datetime.fromtimestamp(NOW, dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    request = {"type": rtype or ("IntentRequest" if intent else "LaunchRequest"), "timestamp": ts}
    if intent:
        request["intent"] = {"name": intent, "slots": {k: {"name": k, "value": v} for k, v in (slots or {}).items()}}
    body = json.dumps(
        {
            "version": "1.0",
            "session": {"attributes": attrs or {}},
            "context": {
                "System": {
                    "application": {"applicationId": SKILL},
                    "user": {"accessToken": tok},
                    "device": {"deviceId": DEVICE},
                }
            },
            "request": request,
        }
    ).encode()
    headers = {
        "signaturecertchainurl": URL,
        "signature-256": sign(env.leaf_key, body),
        "content-type": "application/json",
    }
    r = httpx.post(base + "/v1/alexa", content=body, headers=headers, timeout=10)
    return r.json()


def speech(out):
    return out["response"]["outputSpeech"]["text"]


def ready(world, auto_allowed=False):
    base, env, tmp = world
    auth, tok = link(base)
    bridge = FakeBridge()
    m = Machine(base, auth, tmp, bridge, auto_allowed)
    say(base, env, tok)  # primeiro uso: o dispositivo vira pendente
    httpx.post(base + "/v1/devices/approve", headers=auth, json={"installation_id": m.id, "device_id": DEVICE})
    for _ in range(100):  # espera a maquina conectar
        if "offline" not in speech(say(base, env, tok)):
            break
        time.sleep(0.05)
    return base, env, tok, bridge, m


def test_status_vai_da_alexa_ate_a_ponte_e_volta_com_a_fala(world):
    base, env, tok, bridge, m = ready(world)
    try:
        out = say(base, env, tok, "StatusIntent")
        assert speech(out) == "Nenhum agente em execução."
        method, path, body, secret = bridge.received[-1]
        assert (method, path, body) == ("GET", "/status", None)
        assert secret == "segredo-de-controle-local"  # o segredo e do computador; o relay nunca o conheceu
    finally:
        m.stop()


def test_fluxo_de_aprovacao_usa_a_sessao_da_alexa_e_o_pedido_lido_em_voz_alta(world):
    base, env, tok, bridge, m = ready(world)
    try:
        out = say(base, env, tok, "PendingIntent")
        assert speech(out) == "O claude quer rodar ls." and out["sessionAttributes"]["approval_id"] == 7
        assert out["response"]["reprompt"]["outputSpeech"]["text"] == "Diga aprovar com o seu PIN, ou negar."
        out = say(base, env, tok, "ApproveIntent", {"pin": "1234"}, out["sessionAttributes"])
        assert speech(out) == "Aprovado."
        assert bridge.received[-1][:3] == ("POST", "/decide", {"approve": True, "pin": "1234", "approval_id": 7})
    finally:
        m.stop()


def test_auto_por_voz_e_barrado_ate_o_dono_liberar_no_computador(world):
    base, env, tok, bridge, m = ready(world)
    try:
        out = say(base, env, tok, "SetModeIntent", {"modo": "automatico"})
        assert "relay-auto" in speech(out)
        assert bridge.state["mode"] == "manual"  # a ponte nem foi tocada
        m.auto["on"] = True  # heycode relay-auto on, no computador
        assert say(base, env, tok, "SetModeIntent", {"modo": "automatico"})
        assert bridge.state["mode"] == "auto"
        out = say(base, env, tok, "SetModeIntent", {"modo": "manual"})
        assert speech(out) == "Modo manual ativado." and bridge.state["mode"] == "manual"
    finally:
        m.stop()


def test_computador_que_cai_no_meio_vira_a_frase_acionavel(world):
    base, env, tok, bridge, m = ready(world)
    m.stop()  # o heycode connect parou
    deadline = time.time() + 5
    out = None
    while time.time() < deadline:
        out = say(base, env, tok, "StatusIntent")
        if "offline" in speech(out):
            break
        time.sleep(0.1)
    assert "offline" in speech(out)


def test_dispositivo_nao_aprovado_nunca_chega_a_ponte(world):
    base, env, tmp = world
    auth, tok = link(base)
    bridge = FakeBridge()
    m = Machine(base, auth, tmp, bridge)
    try:
        out = say(base, env, tok, "StatusIntent")
        assert "autorizado" in speech(out)  # dispositivo novo: so vira solicitacao pendente
        assert bridge.received == []
    finally:
        m.stop()


def test_rastro_registra_o_resultado_e_o_detalhe_vem_do_computador(world):
    base, env, tok, bridge, m = ready(world)
    try:
        auth = {
            "Authorization": "Bearer "
            + httpx.post(base + "/v1/login", json={"email": "a@exemplo.com", "password": "senha-bem-longa"}).json()[
                "token"
            ]
        }
        say(base, env, tok, "StatusIntent")
        say(base, env, tok, "SetModeIntent", {"modo": "automatico"})  # barrado: auto nao liberado no computador
        linhas = httpx.get(base + "/v1/audit", headers=auth).json()
        por_tipo = {(r["kind"], r["result"]) for r in linhas}
        assert ("StatusIntent", "ok") in por_tipo and ("SetModeIntent", "barrado") in por_tipo
        assert "automatico" not in str(linhas)  # o que foi dito nao entra no rastro
        detalhe = httpx.get(base + "/v1/audit/detail", params={"installation_id": m.id}, headers=auth)
        assert detalhe.status_code == 200 and detalhe.json()["approvals"][0]["decision"] == "allow"
        assert bridge.received[-1][:2] == ("GET", "/voice/audit?limit=20")
    finally:
        m.stop()


def test_atalho_cadastrado_no_painel_vira_ditado_com_confirmacao_na_ponte(world):
    base, env, tok, bridge, m = ready(world)
    try:
        auth = {
            "Authorization": "Bearer "
            + httpx.post(base + "/v1/login", json={"email": "a@exemplo.com", "password": "senha-bem-longa"}).json()[
                "token"
            ]
        }
        r = httpx.post(
            base + "/v1/commands",
            headers=auth,
            json={
                "name": "rodar testes",
                "aliases": [],
                "agent": "codex",
                "project": "api",
                "instruction": "rode a suite de testes e resuma as falhas",
            },
        )
        assert r.status_code == 201
        out = say(base, env, tok, "RunCommandIntent", {"comando": "rodar os testes"})
        assert speech(out) == "Vou pedir ao codex. Confirma?"
        assert out["response"]["reprompt"]["outputSpeech"]["text"] == "Confirma?"
        assert bridge.received[-1][:3] == (
            "POST",
            "/dictation",
            {"agent": "codex", "text": "rode a suite de testes e resuma as falhas", "project": "api"},
        )
        assert all(c[1] != "/confirm" for c in bridge.received)  # nada foi confirmado nem executado sozinho
        linhas = httpx.get(base + "/v1/audit", headers=auth, params={"limit": 3}).json()
        assert (linhas[0]["kind"], linhas[0]["label"]) == ("RunCommandIntent", "rodar testes")
        assert "suite de testes" not in str(linhas)
        out = say(base, env, tok, "RunCommandIntent", {"comando": "cafe"})
        assert "Não achei" in speech(out)
    finally:
        m.stop()


def test_comando_local_leitura_roda_direto_confirmar_e_pin_seguem_o_fluxo(world):
    base, env, tok, bridge, m = ready(world)
    try:
        out = say(base, env, tok, "RunCommandIntent", {"comando": "ver disco"})
        assert speech(out) == "ver disco terminou com sucesso."  # leitura: sem pergunta
        out = say(base, env, tok, "RunCommandIntent", {"comando": "reiniciar o app"})
        assert out["sessionAttributes"]["pending_command"] == {"risk": "confirmar"} and "Confirma?" in speech(out)
        assert not [c for c in bridge.received if c[1] == "/voice/commands/confirm"]  # nada confirmado ainda
        out = say(base, env, tok, "ConfirmIntent", attrs=out["sessionAttributes"])
        assert speech(out) == "Pronto, comando executado." and "pending_command" not in out["sessionAttributes"]
        out = say(base, env, tok, "RunCommandIntent", {"comando": "deploy"})
        assert out["sessionAttributes"]["pending_command"] == {"risk": "pin"}
        wrong = say(base, env, tok, "ApproveIntent", {"pin": "0000"}, out["sessionAttributes"])
        assert speech(wrong) == "PIN incorreto." and wrong["sessionAttributes"]["pending_command"] == {"risk": "pin"}
        done = say(base, env, tok, "ApproveIntent", {"pin": "1234"}, wrong["sessionAttributes"])
        assert speech(done) == "Pronto, comando executado."
        assert "1234" not in str(done) and "0000" not in str(done)
        auth = {
            "Authorization": "Bearer "
            + httpx.post(base + "/v1/login", json={"email": "a@exemplo.com", "password": "senha-bem-longa"}).json()[
                "token"
            ]
        }
        linhas = httpx.get(base + "/v1/audit", headers=auth, params={"limit": 50}).json()
        assert "ver disco" in {r["label"] for r in linhas} and "1234" not in str(linhas)
    finally:
        m.stop()


def test_painel_lista_e_desliga_comandos_do_computador_e_isola_contas(world):
    base, env, tok, bridge, m = ready(world)
    try:
        auth = {
            "Authorization": "Bearer "
            + httpx.post(base + "/v1/login", json={"email": "a@exemplo.com", "password": "senha-bem-longa"}).json()[
                "token"
            ]
        }
        r = httpx.get(f"{base}/v1/computers/{m.id}/commands", headers=auth)
        assert r.status_code == 200 and [c["name"] for c in r.json()["commands"]] == ["reiniciar app", "deploy"]
        assert "argv" not in r.text and "url" not in r.text
        off = httpx.post(f"{base}/v1/computers/{m.id}/commands/disable", headers=auth, json={"name": "reiniciar app"})
        assert off.status_code == 200 and off.json()["ok"] is True
        assert bridge.received[-1][:3] == ("POST", "/voice/commands/disable", {"name": "reiniciar app"})
        linhas = httpx.get(base + "/v1/audit", headers=auth).json()
        assert ("painel:desligar_comando", "reiniciar app") in {(r["kind"], r["label"]) for r in linhas}
        # nao ha rota para ligar: o painel so consegue desligar
        assert httpx.post(
            f"{base}/v1/computers/{m.id}/commands/enable", headers=auth, json={"name": "x"}
        ).status_code in (404, 405)
        httpx.post(base + "/v1/register", json={"email": "b@exemplo.com", "password": "senha-bem-longa"})
        btok = httpx.post(base + "/v1/login", json={"email": "b@exemplo.com", "password": "senha-bem-longa"}).json()[
            "token"
        ]
        other = {"Authorization": "Bearer " + btok}
        assert httpx.get(f"{base}/v1/computers/{m.id}/commands", headers=other).status_code == 404
        assert (
            httpx.post(
                f"{base}/v1/computers/{m.id}/commands/disable", headers=other, json={"name": "deploy"}
            ).status_code
            == 404
        )
    finally:
        m.stop()


def test_painel_com_computador_offline_diz_503(world):
    base, env, tok, bridge, m = ready(world)
    auth = {
        "Authorization": "Bearer "
        + httpx.post(base + "/v1/login", json={"email": "a@exemplo.com", "password": "senha-bem-longa"}).json()["token"]
    }
    m.stop()
    deadline = time.time() + 5
    code = None
    while time.time() < deadline:
        code = httpx.get(f"{base}/v1/computers/{m.id}/commands", headers=auth).status_code
        if code == 503:
            break
        time.sleep(0.1)
    assert code == 503
