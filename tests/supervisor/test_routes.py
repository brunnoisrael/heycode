import sys
import time

from fastapi import FastAPI, Header, HTTPException
from fastapi.testclient import TestClient

from bridge.store.db import Store
from bridge.supervisor.manager import Supervisor
from bridge.supervisor.routes import make_router


def auth(x_secret: str = Header(default="")):
    if x_secret != "s":
        raise HTTPException(401, "unauthorized")


def make_client():
    store = Store()
    cmds = {a: [sys.executable, "-c", "print('feito')"] for a in ("claude", "codex", "aider")}
    sup = Supervisor(store, cmds)
    app = FastAPI()
    app.include_router(make_router(sup, store, auth))
    return TestClient(app, headers={"x-secret": "s"}), TestClient(app)


def test_401_sem_header():
    _, anon = make_client()
    assert anon.post("/runs", json={"agent": "claude", "prompt": "x"}).status_code == 401
    assert anon.get("/runs/1").status_code == 401
    assert anon.get("/runs/latest").status_code == 401
    assert anon.post("/runs/1/cancel").status_code == 401


def test_post_e_get_run():
    c, _ = make_client()
    rid = c.post("/runs", json={"agent": "claude", "prompt": "oi", "cwd": "."}).json()["run_id"]
    for _ in range(100):
        body = c.get(f"/runs/{rid}").json()
        if body["status"] != "rodando":
            break
        time.sleep(0.1)
    assert body["status"] == "concluida" and "feito" in body["summary"]
    assert c.get("/runs/latest").json()["id"] == rid
    assert c.get("/runs/latest", params={"agent": "claude"}).json()["id"] == rid
    assert c.get("/runs/latest", params={"agent": "aider"}).json() is None


def test_agente_desconhecido_400_e_404():
    c, _ = make_client()
    assert c.post("/runs", json={"agent": "x", "prompt": "oi"}).status_code == 400
    assert c.get("/runs/999").status_code == 404
    assert c.post("/runs/999/cancel").status_code == 404
