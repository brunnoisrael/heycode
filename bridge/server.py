"""Servidor-ponte: recebe eventos dos hooks do Claude Code e responde a skill da Alexa."""
import asyncio, hmac, json, os, re, sys, threading, time, urllib.request
from contextlib import asynccontextmanager
from typing import Literal, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # `uvicorn server:app` e testes

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

from policy.engine import decidir
from policy.rules import NEVER_BY_VOICE  # noqa: F401  (fonte unica; usada via decidir)
from store.db import Store

SECRET = os.environ["BRIDGE_SECRET"]            # obrigatório
PIN = os.environ.get("BRIDGE_PIN", "")          # sem PIN = aprovação por voz desligada
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")   # opcional: push no celular via ntfy.sh
APPROVAL_WAIT = int(os.environ.get("APPROVAL_WAIT", "40"))

DB_PATH = os.environ.get("BRIDGE_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "bridge.db"))
DEFAULT_AGENT = "claude"

store = Store(DB_PATH)
store.expire_pending()  # reinicio: aprovacoes pendentes expiram, sem reanexar


@asynccontextmanager
async def lifespan(_app):
    store.expire_pending()
    yield


app = FastAPI(title="claude-alexa-bridge", lifespan=lifespan)
_summaries: dict = {}  # sid -> ultimo resumo (o store regrava a sessao a cada evento)
lock = {"fails": 0, "until": 0.0}


def auth(x_secret: str = Header(default="")):
    if not hmac.compare_digest(x_secret, SECRET):
        raise HTTPException(401, "unauthorized")


def short(text, n=200):
    text = re.sub(r"\s+", " ", text or "").strip()
    return text[:n] + ("..." if len(text) > n else "")


def push(title: str, body: str):
    if not NTFY_TOPIC:
        return
    def _go():
        try:
            req = urllib.request.Request(f"https://ntfy.sh/{NTFY_TOPIC}", body.encode(), {"Title": title})
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass
    threading.Thread(target=_go, daemon=True).start()


def describe_tool(e: dict) -> str:
    tool, inp = e.get("tool_name", ""), e.get("tool_input") or {}
    if tool == "Bash":  # só a primeira palavra: evita ler segredos em voz alta
        first = (inp.get("command") or "").split()[:1]
        return f"rodando o comando {first[0]}" if first else "rodando um comando"
    if tool in ("Edit", "Write", "MultiEdit"):
        return f"editando {os.path.basename(inp.get('file_path', 'um arquivo'))}"
    if tool == "Read":
        return f"lendo {os.path.basename(inp.get('file_path', 'um arquivo'))}"
    if tool in ("Grep", "Glob"):
        return "procurando no código"
    return f"usando a ferramenta {tool}" if tool else "trabalhando"


def last_assistant_text(path: str) -> str:
    try:
        with open(os.path.expanduser(path), encoding="utf-8") as f:
            lines = f.readlines()
        for line in reversed(lines):
            m = json.loads(line)
            if m.get("type") != "assistant":
                continue
            parts = (m.get("message") or {}).get("content") or []
            text = " ".join(p.get("text", "") for p in parts if isinstance(p, dict) and p.get("type") == "text")
            if text.strip():
                return short(text, 400)
    except Exception:
        pass
    return ""


def project_of(cwd) -> str:
    return os.path.basename(cwd or "") or "projeto"


@app.post("/event", dependencies=[Depends(auth)])
def event(e: dict):
    sid = e.get("session_id", "?")
    agent = e.get("agent") or DEFAULT_AGENT
    project = project_of(e.get("cwd"))
    status, detail = "ocioso", ""
    ev = e.get("hook_event_name")
    if ev == "UserPromptSubmit":
        status, detail = "trabalhando", f"na tarefa: {short(e.get('prompt'), 100)}"
    elif ev == "PreToolUse":
        status, detail = "trabalhando", describe_tool(e)
    elif ev == "Notification":
        status, detail = "aguardando", short(e.get("message"))
        push("Claude precisa de voce", detail)
    elif ev == "Stop":
        status = "concluido"
        _summaries[sid] = last_assistant_text(e.get("transcript_path", ""))
        push("Claude terminou", _summaries[sid] or "Tarefa concluida")
    store.upsert_session(sid, agent, project, status, detail, _summaries.get(sid, ""))
    return {"ok": True}


class ApprovalReq(BaseModel):
    session_id: str = ""
    tool_name: str = ""
    tool_input: Optional[dict] = None
    cwd: str = ""
    agent: str = DEFAULT_AGENT


@app.post("/approval", dependencies=[Depends(auth)])
async def approval(r: ApprovalReq):
    cmd = (r.tool_input or {}).get("command", "")
    cmd = cmd if isinstance(cmd, str) else ""
    project = project_of(r.cwd)
    d = decidir(r.agent, project, r.tool_name, r.tool_input, store)
    if d in ("allow", "deny"):
        return {"decision": d}
    if d != "ask_voz" or not PIN:
        push("Claude precisa de voce", f"Aprovacao manual: {short(cmd or r.tool_name, 120)}")
        return {"decision": "ask"}
    aid = store.add_approval(r.agent, project, r.tool_name, cmd or r.tool_name, r.session_id)
    push("Aprovar por voz?", short(cmd or r.tool_name, 120))
    deadline = time.time() + APPROVAL_WAIT
    while time.time() < deadline:
        decision = store.get_approval(aid)["decision"]
        if decision in ("allow", "deny"):
            return {"decision": decision}
        await asyncio.sleep(0.1)
    if store.get_approval(aid)["decision"] is None:
        store.resolve_approval(aid, "expired")
    decision = store.get_approval(aid)["decision"]
    return {"decision": decision if decision in ("allow", "deny") else "ask"}


class ModeReq(BaseModel):
    mode: Optional[Literal["manual", "auto", "decisoes"]] = None
    report_on_end: Optional[bool] = None
    agent: Optional[str] = None
    project: Optional[str] = None


@app.post("/mode", dependencies=[Depends(auth)])
def set_mode(m: ModeReq):
    store.set_policy(mode=m.mode, report_on_end=m.report_on_end, agent=m.agent, project=m.project)
    return store.get_policy(m.agent, m.project)


@app.get("/mode", dependencies=[Depends(auth)])
def get_mode(agent: Optional[str] = None, project: Optional[str] = None):
    return store.get_policy(agent, project)


@app.get("/status", dependencies=[Depends(auth)])
def status():
    s = store.newest_session()
    if not s:
        return {"speech": "Nenhuma sessão do Claude Code ativa no momento."}
    waiting = store.pending_approvals()
    if waiting:
        return {"speech": f"No projeto {s['project']}, o agente está esperando a sua aprovação."}
    ago = int(time.time() - s["updated"])
    when = "agora" if ago < 10 else f"há {ago // 60} minutos" if ago >= 90 else f"há {ago} segundos"
    detail = f", {s['detail']}" if s["detail"] else ""
    return {"speech": f"No projeto {s['project']}, o agente está {s['status']}{detail}. Última atividade {when}."}


@app.get("/pending", dependencies=[Depends(auth)])
def pending():
    waiting = store.pending_approvals()
    if waiting:
        a = waiting[0]
        return {"actionable": True,
                "speech": f"O agente do projeto {a['project']} quer rodar: {short(a['command'], 160)}. "
                          "Diga aprovar com o seu PIN, ou negar."}
    s = store.newest_session()
    if s and s["status"] == "aguardando":
        return {"actionable": False, "speech": f"O agente precisa de você no teclado: {s['detail']}"}
    return {"actionable": False, "speech": "Nada pendente. O agente não precisa de você agora."}


@app.get("/result", dependencies=[Depends(auth)])
def result():
    s = store.newest_session()
    if s and s["summary"]:
        return {"speech": f"Resumo do projeto {s['project']}: {s['summary']}"}
    return {"speech": "Ainda não há um resumo disponível."}


class Decision(BaseModel):
    approve: bool
    pin: str = ""


@app.post("/decide", dependencies=[Depends(auth)])
def decide(d: Decision):
    if time.time() < lock["until"]:
        return {"speech": "Aprovação por voz bloqueada por alguns minutos. Use o teclado."}
    waiting = store.pending_approvals()
    if not waiting:
        return {"speech": "Não há nada aguardando decisão."}
    if d.approve:
        if not PIN or not hmac.compare_digest(d.pin, PIN):
            lock["fails"] += 1
            if lock["fails"] >= 3:
                lock.update(fails=0, until=time.time() + 300)
                return {"speech": "PIN incorreto três vezes. Aprovação por voz bloqueada por cinco minutos."}
            return {"speech": "PIN incorreto."}
        lock["fails"] = 0
    store.resolve_approval(waiting[0]["id"], "allow" if d.approve else "deny")
    return {"speech": "Aprovado. O agente vai continuar." if d.approve else "Negado. O agente foi informado."}


@app.get("/health")
def health():
    return {"ok": True}
