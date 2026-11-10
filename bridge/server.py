"""Servidor-ponte: recebe eventos dos hooks do Claude Code e responde a skill da Alexa."""
import asyncio, hmac, json, os, re, threading, time, urllib.request, uuid
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

SECRET = os.environ["BRIDGE_SECRET"]            # obrigatório
PIN = os.environ.get("BRIDGE_PIN", "")          # sem PIN = aprovação por voz desligada
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")   # opcional: push no celular via ntfy.sh
APPROVAL_WAIT = int(os.environ.get("APPROVAL_WAIT", "40"))

# Comandos que NUNCA podem ser aprovados por voz (caem no prompt normal do Claude Code)
NEVER_BY_VOICE = [
    r"\brm\b", r"\bsudo\b", r"git\s+push", r"git\s+reset", r"git\s+clean", r"--force", r"\s-f\b",
    r"\bdd\b", r"mkfs", r"chmod\s+-R", r"chown\s+-R", r"\|\s*(sh|bash)\b", r"drop\s+(table|database)",
    r"deploy", r"kubectl\s+delete", r"terraform\s+(apply|destroy)", r"\bshutdown\b|\breboot\b",
]

app = FastAPI(title="claude-alexa-bridge")
sessions: dict = {}
approvals: dict = {}
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


def newest_session():
    return max(sessions.values(), key=lambda s: s["updated"], default=None)


@app.post("/event", dependencies=[Depends(auth)])
def event(e: dict):
    sid = e.get("session_id", "?")
    s = sessions.setdefault(sid, {"project": os.path.basename(e.get("cwd") or "") or "projeto",
                                  "status": "ocioso", "detail": "", "summary": "", "updated": 0})
    s["updated"] = time.time()
    ev = e.get("hook_event_name")
    if ev == "UserPromptSubmit":
        s.update(status="trabalhando", detail=f"na tarefa: {short(e.get('prompt'), 100)}")
    elif ev == "PreToolUse":
        s.update(status="trabalhando", detail=describe_tool(e))
    elif ev == "Notification":
        s.update(status="aguardando", detail=short(e.get("message")))
        push("Claude precisa de voce", short(e.get("message")))
    elif ev == "Stop":
        s.update(status="concluido", detail="", summary=last_assistant_text(e.get("transcript_path", "")))
        push("Claude terminou", s["summary"] or "Tarefa concluida")
    return {"ok": True}


class ApprovalReq(BaseModel):
    session_id: str = ""
    tool_name: str = ""
    tool_input: dict = {}
    cwd: str = ""


@app.post("/approval", dependencies=[Depends(auth)])
async def approval(r: ApprovalReq):
    cmd = (r.tool_input or {}).get("command", "")
    if r.tool_name != "Bash" or not PIN or any(re.search(p, cmd, re.I) for p in NEVER_BY_VOICE):
        push("Claude precisa de voce", f"Aprovacao manual: {short(cmd or r.tool_name, 120)}")
        return {"decision": "ask"}
    aid = uuid.uuid4().hex[:6]
    approvals[aid] = {"event": asyncio.Event(), "decision": None, "command": cmd,
                      "project": os.path.basename(r.cwd) or "projeto", "t": time.time()}
    push("Aprovar por voz?", short(cmd, 120))
    try:
        await asyncio.wait_for(approvals[aid]["event"].wait(), APPROVAL_WAIT)
    except asyncio.TimeoutError:
        pass
    return {"decision": approvals.pop(aid)["decision"] or "ask"}


@app.get("/status", dependencies=[Depends(auth)])
def status():
    s = newest_session()
    if not s:
        return {"speech": "Nenhuma sessão do Claude Code ativa no momento."}
    waiting = [a for a in approvals.values() if a["decision"] is None]
    if waiting:
        return {"speech": f"No projeto {s['project']}, o agente está esperando a sua aprovação."}
    ago = int(time.time() - s["updated"])
    when = "agora" if ago < 10 else f"há {ago // 60} minutos" if ago >= 90 else f"há {ago} segundos"
    detail = f", {s['detail']}" if s["detail"] else ""
    return {"speech": f"No projeto {s['project']}, o agente está {s['status']}{detail}. Última atividade {when}."}


@app.get("/pending", dependencies=[Depends(auth)])
def pending():
    waiting = sorted((a for a in approvals.values() if a["decision"] is None), key=lambda a: a["t"])
    if waiting:
        a = waiting[0]
        return {"actionable": True,
                "speech": f"O agente do projeto {a['project']} quer rodar: {short(a['command'], 160)}. "
                          "Diga aprovar com o seu PIN, ou negar."}
    s = newest_session()
    if s and s["status"] == "aguardando":
        return {"actionable": False, "speech": f"O agente precisa de você no teclado: {s['detail']}"}
    return {"actionable": False, "speech": "Nada pendente. O agente não precisa de você agora."}


@app.get("/result", dependencies=[Depends(auth)])
def result():
    s = newest_session()
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
    waiting = sorted((a for a in approvals.values() if a["decision"] is None), key=lambda a: a["t"])
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
    waiting[0]["decision"] = "allow" if d.approve else "deny"
    waiting[0]["event"].set()
    return {"speech": "Aprovado. O agente vai continuar." if d.approve else "Negado. O agente foi informado."}


@app.get("/health")
def health():
    return {"ok": True}
