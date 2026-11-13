import pytest
from fastapi import FastAPI, Header, HTTPException
from fastapi.testclient import TestClient

from heycode.dictation.routes import make_router
from heycode.dictation.service import Dictation
from heycode.policy.redact import mask_secrets

SK = "sk-abcdef1234567890XYZ"


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


@pytest.fixture
def env():
    clock = Clock()
    calls = []

    def start_run(agent, text, project):
        calls.append((agent, text, project))
        return 42

    return Dictation(start_run, clock=clock), clock, calls


@pytest.mark.parametrize("raw,secret", [
    ("use " + SK + " aqui", SK),
    ("token ghp_abcdefghijklmnopqrstuvwxyz0123456789 ok", "ghp_abcdefghijklmnopqrstuvwxyz0123456789"),
    ("chave AKIAIOSFODNN7EXAMPLE fim", "AKIAIOSFODNN7EXAMPLE"),
    ("conecte com password=hunter2 agora", "hunter2"),
    ("pat github_pat_11ABCDEFG0abcdefghijklmnop_xyz fim", "github_pat_11ABCDEFG0abcdefghijklmnop_xyz"),
    ("chave temporaria ASIAIOSFODNN7EXAMPLE fim", "ASIAIOSFODNN7EXAMPLE"),
])
def test_ditado_mascara_pela_funcao_unificada(env, raw, secret):
    d, _, _ = env
    r = d.propose("claude", raw)
    assert secret not in r["speech"]
    assert "[segredo]" in r["speech"]


def test_ditado_texto_normal_intacto(env):
    d, _, _ = env
    assert "corrija o bug do login" in d.propose("claude", "corrija o bug do login")["speech"]


def test_ditado_nao_tem_mascara_local():
    import heycode.dictation.service as svc
    assert not hasattr(svc, "_mask") and svc.mask_secrets is mask_secrets


def test_propose_masks_speech_but_keeps_original(env):
    d, _, calls = env
    r = d.propose("claude", "use " + SK + " no deploy")
    assert r["ok"] is True
    assert SK not in r["speech"]
    assert "[segredo]" in r["speech"]
    assert "claude" in r["speech"].lower()
    d.confirm()
    assert calls == [("claude", "use " + SK + " no deploy", None)]


@pytest.mark.parametrize("text", ["", "   "])
def test_propose_empty(env, text):
    d, _, _ = env
    assert d.propose("claude", text)["ok"] is False


def test_propose_length_limit(env):
    d, _, _ = env
    assert d.propose("claude", "a" * 300)["ok"] is True
    assert d.propose("claude", "a" * 301)["ok"] is False


def test_failed_propose_does_not_leave_pending(env):
    d, _, calls = env
    d.propose("claude", "a" * 301)
    assert "run_id" not in d.confirm()
    assert calls == []


def test_confirm_without_pending(env):
    d, _, calls = env
    r = d.confirm()
    assert "run_id" not in r
    assert "nada" in r["speech"].lower()
    assert calls == []


def test_confirm_after_expiry(env):
    d, clock, calls = env
    d.propose("codex", "faca x")
    clock.t += 61
    r = d.confirm()
    assert "run_id" not in r
    assert "expir" in r["speech"].lower()
    assert calls == []


def test_confirm_at_ttl_boundary_valid(env):
    d, clock, calls = env
    d.propose("codex", "faca x")
    clock.t += 60
    assert d.confirm()["run_id"] == 42


def test_second_propose_replaces_first(env):
    d, _, calls = env
    d.propose("claude", "primeiro")
    d.propose("aider", "segundo", "proj")
    d.confirm()
    assert calls == [("aider", "segundo", "proj")]


def test_confirm_once_only(env):
    d, _, calls = env
    d.propose("claude", "faca x")
    assert d.confirm()["run_id"] == 42
    assert "run_id" not in d.confirm()
    assert len(calls) == 1


def test_cancel(env):
    d, _, calls = env
    d.propose("claude", "faca x")
    assert "cancel" in d.cancel()["speech"].lower()
    assert "run_id" not in d.confirm()
    assert calls == []


def test_cancel_without_pending(env):
    d, _, _ = env
    assert "nada" in d.cancel()["speech"].lower()


def test_start_run_failure_does_not_raise():
    def boom(*a):
        raise RuntimeError(SK)

    d = Dictation(boom, clock=Clock())
    d.propose("claude", "x")
    r = d.confirm()
    assert "run_id" not in r
    assert SK not in r["speech"]


def _client(d):
    def auth(x_secret: str = Header(default="")):
        if x_secret != "s":
            raise HTTPException(401, "unauthorized")

    app = FastAPI()
    app.include_router(make_router(d, auth))
    return TestClient(app)


def test_routes_require_auth(env):
    c = _client(env[0])
    assert c.post("/dictation", json={"agent": "claude", "text": "x"}).status_code == 401
    assert c.post("/dictation/confirm").status_code == 401
    assert c.post("/dictation/cancel").status_code == 401


def test_routes_flow(env):
    d, _, calls = env
    c = _client(d)
    h = {"x-secret": "s"}
    r = c.post("/dictation", json={"agent": "claude", "text": "use " + SK, "project": "p"}, headers=h)
    assert r.status_code == 200 and r.json()["ok"] is True
    assert SK not in r.text
    r = c.post("/dictation/confirm", headers=h)
    assert r.json()["run_id"] == 42
    assert calls == [("claude", "use " + SK, "p")]
    assert c.post("/dictation/cancel", headers=h).status_code == 200


def test_routes_unknown_agent(env):
    c = _client(env[0])
    r = c.post("/dictation", json={"agent": "gpt", "text": "x"}, headers={"x-secret": "s"})
    assert r.status_code == 200 and r.json()["ok"] is False
