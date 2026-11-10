import asyncio
import json
import socket
import threading
import time

import pytest


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def tools(client):
    return client.server.mcp_mod.make_tools(client.server.store, lambda: client.server.APPROVAL_WAIT)


def _wait_pending(store):
    for _ in range(100):
        if store.pending_approvals():
            return
        time.sleep(0.05)


def test_registrar_status(client, tools):
    r = run(tools.registrar_status("trabalhando", "compilando", "codex", "proj"))
    assert r["ok"] is True
    s = client.server.store.newest_session()
    assert (s["agent"], s["project"], s["status"], s["detail"]) == ("codex", "proj", "trabalhando", "compilando")


def test_reportar_fim(client, tools):
    run(tools.reportar_fim("tudo pronto", "codex", "proj"))
    s = client.server.store.newest_session()
    assert s["status"] == "concluido" and s["summary"] == "tudo pronto"
    assert client.get("/result").json()["speech"].endswith("tudo pronto")


def test_buscar_instrucao(client, tools):
    st = client.server.store
    st.add_instruction("um", "codex", "proj")
    st.add_instruction("dois", "codex", "proj")
    assert run(tools.buscar_instrucao("codex", "proj")) == {"instruction": "um"}
    assert run(tools.buscar_instrucao("codex", "proj")) == {"instruction": "dois"}
    assert run(tools.buscar_instrucao("codex", "proj")) == {"instruction": None}


def test_pedir_decisao_auto(client, tools):
    client.post("/mode", json={"mode": "auto"})
    assert run(tools.pedir_decisao("posso?")) == {"answer": "sim", "auto": True}


def test_pedir_decisao_sem_resposta(client, tools):
    t0 = time.time()
    assert run(tools.pedir_decisao("posso?")) == {"answer": "sem_resposta"}
    assert time.time() - t0 < 5
    assert client.server.store.pending_approvals() == []


def test_pedir_decisao_resolvida_por_decide(client, tools):
    out = {}
    th = threading.Thread(target=lambda: out.update(r=run(tools.pedir_decisao("subir?", "a", "p"))))
    th.start()
    _wait_pending(client.server.store)
    ap = client.server.store.pending_approvals()[0]
    assert ap["tool"] == "pedir_decisao" and ap["command"] == "subir?"
    client.post("/decide", json={"approve": True, "pin": "1234"})
    th.join(5)
    assert out["r"] == {"answer": "sim"}


def test_pedir_decisao_negada(client, tools):
    out = {}
    th = threading.Thread(target=lambda: out.update(r=run(tools.pedir_decisao("subir?"))))
    th.start()
    _wait_pending(client.server.store)
    client.post("/decide", json={"approve": False})
    th.join(5)
    assert out["r"] == {"answer": "nao"}


def test_mcp_sem_credencial_401(client):
    assert client.post("/mcp", headers={"x-secret": ""}, json={}).status_code == 401
    assert client.post("/mcp", headers={"x-secret": "errado"}, json={}).status_code == 401
    assert client.post("/mcp", headers={"x-secret": "", "Authorization": "Bearer errado"}, json={}).status_code == 401


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_cliente_mcp_real(client):
    """Cliente MCP do SDK contra /mcp num uvicorn em porta livre (lifespan real)."""
    import uvicorn
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    port = _free_port()
    srv = uvicorn.Server(uvicorn.Config(client.server.app, host="127.0.0.1", port=port, log_level="error"))
    th = threading.Thread(target=srv.run, daemon=True)
    th.start()
    for _ in range(100):
        if srv.started:
            break
        time.sleep(0.05)
    assert srv.started
    client.server.store.add_instruction("va", "claude", "demo")

    async def go():
        async with streamablehttp_client(
                f"http://127.0.0.1:{port}/mcp", headers={"Authorization": "Bearer s"}) as (r, w, _):
            async with ClientSession(r, w) as sess:
                await sess.initialize()
                names = {t.name for t in (await sess.list_tools()).tools}
                res = await sess.call_tool("buscar_instrucao", {"agent": "claude", "project": "demo"})
                await sess.call_tool("registrar_status", {"status": "ok", "agent": "claude", "project": "demo"})
                return names, json.loads(res.content[0].text)

    try:
        names, content = run(go())
    finally:
        srv.should_exit = True
        th.join(5)
    assert names == {"registrar_status", "pedir_decisao", "reportar_fim", "buscar_instrucao"}
    assert content == {"instruction": "va"}
    assert client.server.store.newest_session()["project"] == "demo"
