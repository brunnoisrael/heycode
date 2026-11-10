"""Servidor MCP "roomcode" (ADR 0006): ferramentas que qualquer agente com cliente MCP usa na ponte.

Este arquivo e carregado por `bridge/server.py` via importlib (o pacote `bridge/mcp` faria sombra
ao SDK `mcp` se `bridge/` estiver no sys.path), com o SDK ja presente em sys.modules.
"""
import asyncio
import hmac
import time
from types import SimpleNamespace

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.responses import PlainTextResponse

from policy.engine import decidir


def make_tools(store, approval_wait):
    """Funcoes das ferramentas, ligadas a um Store. `approval_wait()` devolve o prazo em segundos."""

    async def registrar_status(status: str, detail: str = "", agent: str = "agent", project: str = "projeto") -> dict:
        """Registra o estado atual do agente (ex.: trabalhando, aguardando) para a Alexa informar."""
        store.upsert_session(f"mcp:{agent}:{project}", agent, project, status, detail, None)
        return {"ok": True}

    async def pedir_decisao(question: str, agent: str = "agent", project: str = "projeto") -> dict:
        """Pergunta ao dono (por voz) uma decisao sim/nao. Retorna answer: sim, nao ou sem_resposta."""
        if decidir(agent, project, "pedir_decisao", {"command": question}, store) == "allow":
            return {"answer": "sim", "auto": True}
        aid = store.add_approval(agent, project, "pedir_decisao", question, f"mcp:{agent}:{project}")
        deadline = time.time() + approval_wait()
        while time.time() < deadline:
            decision = store.get_approval(aid)["decision"]
            if decision in ("allow", "deny"):
                return {"answer": "sim" if decision == "allow" else "nao"}
            await asyncio.sleep(0.1)
        if store.get_approval(aid)["decision"] is None:
            store.resolve_approval(aid, "expired")
        decision = store.get_approval(aid)["decision"]
        return {"answer": {"allow": "sim", "deny": "nao"}.get(decision, "sem_resposta")}

    async def reportar_fim(summary: str, agent: str = "agent", project: str = "projeto") -> dict:
        """Informa que a tarefa terminou, com um resumo curto para a Alexa ler."""
        store.upsert_session(f"mcp:{agent}:{project}", agent, project, "concluido", "", summary)
        return {"ok": True}

    async def buscar_instrucao(agent: str = "agent", project: str = "projeto") -> dict:
        """Busca a proxima instrucao enviada pelo dono (cada uma e entregue uma unica vez)."""
        item = store.pop_instruction(agent, project)
        return {"instruction": item["text"] if item else None}

    return SimpleNamespace(registrar_status=registrar_status, pedir_decisao=pedir_decisao,
                           reportar_fim=reportar_fim, buscar_instrucao=buscar_instrucao)


def build_mcp(tools) -> FastMCP:
    # Rota em /mcp dentro do sub-app; auth por bearer cobre o DNS rebinding.
    mcp = FastMCP(
        "roomcode", streamable_http_path="/mcp", stateless_http=True, json_response=True,
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False))
    for fn in (tools.registrar_status, tools.pedir_decisao, tools.reportar_fim, tools.buscar_instrucao):
        mcp.tool()(fn)
    return mcp


class SecretAuth:
    """Middleware ASGI: so exige credencial em /mcp (Authorization: Bearer ou x-secret)."""

    def __init__(self, app, secret: str):
        self.app, self.secret = app, secret

    def _ok(self, headers: dict) -> bool:
        bearer = headers.get("authorization", "")
        token = bearer[7:] if bearer.lower().startswith("bearer ") else ""
        return any(hmac.compare_digest(c.encode(), self.secret.encode())
                   for c in (token, headers.get("x-secret", "")))

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["path"].startswith("/mcp"):
            headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]}
            if not self._ok(headers):
                await PlainTextResponse("unauthorized", status_code=401)(scope, receive, send)
                return
        await self.app(scope, receive, send)
