"""Servidor-ponte: recebe eventos dos hooks do Claude Code e responde a skill da Alexa."""
import asyncio, hmac, importlib.util, json, os, re, secrets, sys, threading, time, urllib.request
from contextlib import asynccontextmanager
from typing import Literal, Optional

_BRIDGE_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_mcp_module():
    """Carrega bridge/mcp/server.py sem deixar o pacote `bridge/mcp` fazer sombra ao SDK `mcp`."""
    saved = sys.path[:]
    try:  # importa o SDK com bridge/ (e cwd == bridge/) fora do sys.path; depois fica em sys.modules
        sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.getcwd()) != _BRIDGE_DIR]
        for name in [n for n in sys.modules if n == "mcp" or n.startswith("mcp.")]:
            if os.path.abspath(getattr(sys.modules[name], "__file__", "") or "").startswith(os.path.join(_BRIDGE_DIR, "mcp")):
                del sys.modules[name]  # sombra de import anterior
        import mcp.server.fastmcp  # noqa: F401
    finally:
        sys.path[:] = saved
    spec = importlib.util.spec_from_file_location("roomcode_mcp", os.path.join(_BRIDGE_DIR, "mcp", "server.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sys.path.insert(0, _BRIDGE_DIR)  # `uvicorn server:app` e testes

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from policy.engine import decidir
from policy.rules import NEVER_BY_VOICE  # noqa: F401  (fonte unica; usada via decidir)
from store.db import Store
from policy.redact import mask_secrets
from supervisor.manager import Supervisor
from supervisor.failure import spoken_reason
from supervisor.routes import make_router as _runs_router, resolve_under_root
from dictation.service import Dictation
from dictation.routes import make_router as _dictation_router
from projects.service import ProjectCreator
from projects.routes import make_router as _projects_router
from projects.activity import make_router as _activity_router

MIN_SECRET_LEN = 32


def _require_secret(name: str) -> str:
    value = os.environ.get(name, "")
    if len(value) < MIN_SECRET_LEN:  # M7: segredo vazio/curto abriria a ponte (compare_digest("", "") e verdadeiro)
        raise SystemExit(f"{name} ausente ou com menos de {MIN_SECRET_LEN} caracteres: a ponte nao inicia.")
    return value


SECRET = _require_secret("BRIDGE_SECRET")                  # segredo de AGENTE: hooks e MCP (ADR 0014)
CONTROL_SECRET = _require_secret("BRIDGE_CONTROL_SECRET")  # segredo de CONTROLE: so a Lambda
if hmac.compare_digest(SECRET.encode(), CONTROL_SECRET.encode()):
    raise SystemExit("BRIDGE_SECRET e BRIDGE_CONTROL_SECRET precisam ser diferentes.")
PIN = os.environ.get("BRIDGE_PIN", "")          # sem PIN = aprovação por voz desligada
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")   # opcional: push no celular via ntfy.sh
HA_WEBHOOK_URL = os.environ.get("HA_WEBHOOK_URL", "")  # opcional: webhook (Home Assistant) para voz espontanea
APPROVAL_WAIT = int(os.environ.get("APPROVAL_WAIT", "40"))
OPEN_SESSION_WINDOW = int(os.environ.get("OPEN_SESSION_WINDOW", "1800"))  # s sem evento: a sessao nao conta como aberta
INSTRUCTION_TTL = int(os.environ.get("INSTRUCTION_TTL", "1800"))  # s: instrucao na fila nao entregue expira

DB_PATH = os.environ.get("BRIDGE_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "bridge.db"))
DEFAULT_AGENT = "claude"

PROJECTS_ROOT = os.environ.get("PROJECTS_ROOT", os.path.expanduser(os.path.join("~", "Documents", "Projetos")))

store = Store(DB_PATH)
store.expire_pending()  # reinicio: aprovacoes pendentes expiram, sem reanexar
store.interrupt_running()  # reinicio: runs do supervisor em andamento viram "interrompida", sem reanexar


mcp_mod = _load_mcp_module()
_tools = mcp_mod.make_tools(store, lambda: APPROVAL_WAIT, lambda: bool(PIN), lambda: INSTRUCTION_TTL)
_mcp_current = {"app": None}  # sub-app MCP da execucao atual do lifespan (o gerenciador de sessao roda uma vez so)


async def _mcp_dispatch(scope, receive, send):
    sub = _mcp_current["app"]
    if sub is None:  # fora do lifespan (ex.: TestClient sem `with`)
        from starlette.responses import PlainTextResponse
        await PlainTextResponse("mcp indisponivel", status_code=503)(scope, receive, send)
        return
    await sub(scope, receive, send)


@asynccontextmanager
async def lifespan(_app):
    store.expire_pending()
    # Mount nao executa o lifespan do sub-app: o gerenciador de sessao do MCP sobe junto com a app.
    mcp_server = mcp_mod.build_mcp(_tools)
    previous = _mcp_current["app"]
    _mcp_current["app"] = mcp_server.streamable_http_app()
    try:
        async with mcp_server.session_manager.run():
            yield
    finally:
        _mcp_current["app"] = previous


app = FastAPI(title="roomcode", lifespan=lifespan)


def _check(x_secret: str, expected: str):
    if not hmac.compare_digest(x_secret.encode(), expected.encode()):
        raise HTTPException(401, "unauthorized")


def auth_agent(x_secret: str = Header(default="")):
    """Rotas dos agentes (hooks): /event, /approval, /instruction/next."""
    _check(x_secret, SECRET)


def auth_control(x_secret: str = Header(default="")):
    """Rotas de controle (Lambda): todo o resto, exceto /health."""
    _check(x_secret, CONTROL_SECRET)


def say(text) -> str:
    """Unico caminho de toda `speech`: nenhum segredo e lido em voz alta."""
    return mask_secrets(text if isinstance(text, str) else str(text))


def short(text, n=200):
    text = re.sub(r"\s+", " ", text or "").strip()
    return text[:n] + ("..." if len(text) > n else "")


def push(title: str, body: str):
    """Aviso proativo: ntfy (push no celular) e/ou webhook (ex.: Home Assistant). Nunca levanta; segredos mascarados."""
    ntfy, hook = NTFY_TOPIC, HA_WEBHOOK_URL
    if not (ntfy or hook):
        return
    title, body = mask_secrets(title), mask_secrets(body)

    def _go():
        if ntfy:
            try:
                urllib.request.urlopen(urllib.request.Request(
                    f"https://ntfy.sh/{ntfy}", body.encode(), {"Title": title.encode("ascii", "ignore").decode()}), timeout=5)
            except Exception:
                pass
        if hook:
            try:
                urllib.request.urlopen(urllib.request.Request(
                    hook, json.dumps({"title": title, "message": body}).encode(),
                    {"Content-Type": "application/json"}), timeout=5)
            except Exception:
                pass
    threading.Thread(target=_go, daemon=True).start()


def describe_tool(e: dict) -> str:
    tool, inp = e.get("tool_name", ""), e.get("tool_input") or {}
    if tool == "Bash":  # só a primeira palavra (depois de VAR=valor): evita ler segredos em voz alta
        words = (inp.get("command") or "").split()
        while words and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[0]):
            words.pop(0)
        first = words[:1]
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


# --- Supervisor e ditado (fase 4) ---
# fim de ciclo nao lido: coluna runs.reported (ADR 0015), sobrevive a reinicio


def _failure_speech(run: dict) -> str:
    """Fala de uma run que falhou (ADR 0017): motivo curto, sem JSON cru; a mascara fica com `say`."""
    base = f"O agente {run['agent']} falhou no projeto {run['project']}"
    reason = spoken_reason(run.get("summary"))
    if not reason:
        return f"{base}. Não consegui identificar o motivo; veja a saída no computador."
    return f"{base}: {reason}" + ("" if reason[-1] in ".!?" else ".")


def _take_failure() -> str:
    """Se o proximo aviso da fila for uma falha, marca como falado e devolve a fala; senao, ""."""
    run = store.first_unreported()
    if not run or run["status"] != "falhou":
        return ""
    store.mark_reported(run["id"])
    return _failure_speech(run)


def _take_finished() -> str:
    """Proximo aviso da fila, falha ou resultado (ADR 0019): marca como falado e devolve a fala; senao, ""."""
    failed = _take_failure()
    if failed:
        return failed
    run = store.first_unreported()
    if not run or run["status"] != "concluida":
        return ""
    store.mark_reported(run["id"])
    result = (run.get("summary") or "sem resumo").strip()
    return (f"O agente {run['agent']} terminou no projeto {run['project']}. Resultado: {result}"
            + ("" if result[-1] in ".!?" else "."))


_voice_runs: set[int] = set()  # runs pedidas por voz ainda em andamento (ADR 0019); reinicio as interrompe


def _on_run_finished(run: dict):
    failed = run.get("status") == "falhou"
    if failed:
        push(f"{run['agent']} falhou", spoken_reason(run.get("summary")) or "Falhou sem motivo identificado")
    else:
        push(f"{run['agent']} terminou", short(run.get("summary") or "Tarefa concluida"))
    by_voice = run["id"] in _voice_runs
    _voice_runs.discard(run["id"])
    # falha sempre entra na fila de voz (ADR 0017); sucesso pedido por voz tambem (ADR 0019);
    # o resto (run direta, cancelada) so com report_on_end
    if failed or (by_voice and run.get("status") == "concluida") \
            or store.get_policy(run["agent"], run["project"])["report_on_end"]:
        store.mark_unreported(run["id"])


def _resolve_project(project):
    """Pasta do projeto dentro de PROJECTS_ROOT (realpath + commonpath) ou None. Sem projeto: a raiz."""
    root = os.path.realpath(PROJECTS_ROOT)
    if not project:
        return root
    path = resolve_under_root(root, os.path.join(root, project))
    return path if path and path != root else None  # "." nao e um projeto


def _check_project(project):
    """Fala de erro para o ditado quando o projeto citado nao existe (nunca cai na raiz); None se ok."""
    if project and _resolve_project(project) is None:
        return f"Não achei o projeto {project}."
    return None


supervisor = Supervisor(store, on_finish=_on_run_finished)


def _start_run(agent: str, text: str, project) -> int:
    cwd = _resolve_project(project)
    if cwd is None:
        raise ValueError(f"projeto nao encontrado: {project}")
    mode = store.get_policy(agent, project_of(cwd))["mode"]  # politica sempre do cwd final
    run_id = supervisor.start(agent, text, cwd, mode)
    _voice_runs.add(run_id)  # caminho unico da voz (ditado e projeto novo): o fim volta por voz (ADR 0019)
    return run_id


def _open_session():
    """Sessao aberta mais recente (eventos dos hooks ou `registrar_status`) com atividade na janela; ou None."""
    s = store.newest_session()
    if not s or time.time() - s["updated"] > OPEN_SESSION_WINDOW:
        return None
    return s


def _enqueue_instruction(agent: str, text: str, project) -> int:
    return store.add_instruction(text, agent, project)


dictation = Dictation(_start_run, check_project=_check_project,
                      open_session=_open_session, enqueue=_enqueue_instruction)
_TEMPLATE_REPO = os.path.dirname(_BRIDGE_DIR)  # este repositorio: fonte de scripts/gates e .githooks
project_creator = ProjectCreator(PROJECTS_ROOT, _TEMPLATE_REPO, _start_run)


@app.post("/event", dependencies=[Depends(auth_agent)])
def event(e: dict):
    sid = e.get("session_id", "?")
    agent = e.get("agent") or DEFAULT_AGENT
    project = project_of(e.get("cwd"))
    status, detail, summary = "ocioso", "", None
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
        summary = last_assistant_text(e.get("transcript_path", ""))
        push("Claude terminou", summary or "Tarefa concluida")
    store.upsert_session(sid, agent, project, status, detail, summary)  # None preserva o resumo gravado
    return {"ok": True}


class ApprovalReq(BaseModel):
    session_id: str = ""
    tool_name: str = ""
    tool_input: Optional[dict] = None
    cwd: str = ""
    agent: str = DEFAULT_AGENT


@app.post("/approval", dependencies=[Depends(auth_agent)])
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


class InstructionReq(BaseModel):
    text: str = Field(min_length=1, max_length=300)
    agent: str = DEFAULT_AGENT
    project: Optional[str] = None


@app.post("/instruction", dependencies=[Depends(auth_control)])
def add_instruction(i: InstructionReq):
    return {"id": store.add_instruction(i.text, i.agent, i.project)}


class NextInstructionReq(BaseModel):
    agent: str
    project: Optional[str] = None


@app.post("/instruction/next", dependencies=[Depends(auth_agent)])
def next_instruction(r: NextInstructionReq):
    item = store.pop_instruction(r.agent, r.project, INSTRUCTION_TTL)
    return {"instruction": item["text"] if item else None}


class ModeReq(BaseModel):
    mode: Optional[Literal["manual", "auto", "decisoes"]] = None
    report_on_end: Optional[bool] = None
    agent: Optional[str] = None
    project: Optional[str] = None


_MODE_NAMES = {"manual": "manual", "auto": "automático", "decisoes": "decisões"}


def _scope(agent, project) -> str:
    if project:
        return f"para o projeto {project}"
    if agent:
        return f"para o agente {agent}"
    return "para todos os agentes"


def _mode_reply(agent, project, spoken: str) -> dict:
    p = store.get_policy(agent, project)
    return {"mode": p["mode"], "report_on_end": p["report_on_end"], "speech": say(spoken)}


@app.post("/mode", dependencies=[Depends(auth_control)])
def set_mode(m: ModeReq):
    store.set_policy(mode=m.mode, report_on_end=m.report_on_end, agent=m.agent, project=m.project)
    scope, parts = _scope(m.agent, m.project), []
    if m.mode:
        parts.append(f"Modo {_MODE_NAMES[m.mode]} ativado {scope}.")
    if m.report_on_end is not None:
        parts.append("Aviso de fim de ciclo ligado." if m.report_on_end else "Aviso de fim de ciclo desligado.")
    if not parts:
        parts.append("Nada foi alterado.")
    return _mode_reply(m.agent, m.project, " ".join(parts))


@app.get("/mode", dependencies=[Depends(auth_control)])
def get_mode(agent: Optional[str] = None, project: Optional[str] = None):
    p = store.get_policy(agent, project)
    fim = "ligado" if p["report_on_end"] else "desligado"
    return _mode_reply(agent, project,
                       f"O modo atual é {_MODE_NAMES.get(p['mode'], p['mode'])}. Aviso de fim de ciclo {fim}.")


@app.get("/status", dependencies=[Depends(auth_control)])
def status():
    s = store.newest_session()
    if not s:
        return {"speech": say(_take_finished()) or "Nenhuma sessão do Claude Code ativa no momento."}
    waiting = store.pending_approvals()
    if waiting:
        return {"speech": say(f"No projeto {s['project']}, o agente está esperando a sua aprovação.")}
    ago = int(time.time() - s["updated"])
    when = "agora" if ago < 10 else f"há {ago // 60} minutos" if ago >= 90 else f"há {ago} segundos"
    detail = f", {s['detail']}" if s["detail"] else ""
    failed = _take_finished()  # falha ou resultado ainda nao falado vem antes do status da sessao (ADR 0017, 0019)
    return {"speech": say(f"{failed} No projeto {s['project']}, o agente está {s['status']}{detail}. "
                          f"Última atividade {when}.".strip())}


@app.get("/pending", dependencies=[Depends(auth_control)])
def pending():
    waiting = store.pending_approvals()
    if waiting:
        a = waiting[0]
        if a['tool'] == 'pedir_resposta':
            return {"actionable": True, "kind": "question", "approval_id": a['id'],
                    "speech": say(f"O agente do projeto {a['project']} pergunta: {short(a['command'], 160)}. Diga responder.")}
        return {"actionable": True, "approval_id": a["id"],
                "speech": say(f"O agente do projeto {a['project']} quer rodar: {short(a['command'], 160)}. "
                              "Diga aprovar com o seu PIN, ou negar.")}
    failed = _take_failure()
    if failed:
        return {"actionable": False, "approval_id": None, "speech": say(failed)}
    run = store.first_unreported()
    if run:
        return {"actionable": False, "approval_id": None,
                "speech": say(f"O agente {run['agent']} terminou no projeto {run['project']}. Quer ouvir a saída?")}
    s = store.newest_session()
    if s and s["status"] == "aguardando":
        return {"actionable": False, "approval_id": None,
                "speech": say(f"O agente precisa de você no teclado: {s['detail']}")}
    return {"actionable": False, "approval_id": None, "speech": "Nada pendente. O agente não precisa de você agora."}


@app.get("/result", dependencies=[Depends(auth_control)])
def result():
    failed = _take_failure()
    if failed:
        return {"speech": say(failed)}
    run = store.first_unreported()
    if run:
        store.mark_reported(run["id"])
        outcome = "falhou" if run["status"] == "falhou" else "terminou"
        return {"speech": say(f"O agente {run['agent']} {outcome} no projeto {run['project']}. "
                              f"Resultado: {run.get('summary') or 'sem resumo'}")}
    s = store.newest_session()
    if s and s["summary"]:
        return {"speech": say(f"Resumo do projeto {s['project']}: {s['summary']}")}
    return {"speech": "Ainda não há um resumo disponível."}


class Decision(BaseModel):
    approve: bool
    pin: str = ""
    approval_id: Optional[int] = None


class FreeAnswer(BaseModel):
    approval_id: int
    text: str


class ConfirmFreeAnswer(BaseModel):
    approval_id: int
    token: str


_answer_lock = threading.Lock()
_answer_drafts = {}


@app.post("/answer/preview", dependencies=[Depends(auth_control)])
def preview_answer(d: FreeAnswer):
    text = d.text.strip()
    if not text or len(text) > 300:
        return {"ok": False, "speech": "Diga uma resposta de até 300 caracteres."}
    waiting = store.pending_approvals()
    if (not waiting or waiting[0]['id'] != d.approval_id or waiting[0]['tool'] != 'pedir_resposta'
            or time.time() - waiting[0]['t'] >= APPROVAL_WAIT):
        return {"ok": False, "speech": "Essa pergunta mudou ou expirou. Pergunte novamente."}
    token = secrets.token_urlsafe(32)
    with _answer_lock:
        now = time.time()
        for key in list(_answer_drafts):
            if _answer_drafts[key]['deadline'] <= now:
                del _answer_drafts[key]
        _answer_drafts[d.approval_id] = {'token': token, 'text': text, 'deadline': waiting[0]['t'] + APPROVAL_WAIT}
    return {"ok": True, "token": token, "speech": say(f"Entendi: {text}. Confirma?")}


@app.post("/answer/confirm", dependencies=[Depends(auth_control)])
def confirm_answer(d: ConfirmFreeAnswer):
    with _answer_lock:
        draft = _answer_drafts.get(d.approval_id)
        if not draft or not hmac.compare_digest(draft['token'], d.token):
            return {"ok": False, "speech": "Essa resposta mudou ou expirou. Nada foi enviado."}
        del _answer_drafts[d.approval_id]
    if time.time() >= draft['deadline'] or not store.answer_question(d.approval_id, draft['text'], APPROVAL_WAIT):
        return {"ok": False, "speech": "Essa pergunta mudou ou expirou. Nada foi enviado."}
    return {"ok": True, "speech": "Resposta enviada ao agente."}


@app.post("/decide", dependencies=[Depends(auth_control)])
def decide(d: Decision):
    lock = store.get_pin_lock()
    if time.time() < lock["until"]:
        return {"speech": "Aprovação por voz bloqueada por alguns minutos. Use o teclado."}
    waiting = store.pending_approvals()
    if d.approval_id is not None:  # A4: a decisao vale so para o pedido que o dono ouviu
        seen = store.get_approval(d.approval_id)
        if seen and seen["decision"] == "expired":
            return {"speech": "Esse pedido já expirou."}
        if not waiting or waiting[0]["id"] != d.approval_id:
            return {"speech": "Esse pedido mudou. Pergunte de novo."}
    if not waiting:
        return {"speech": "Não há nada aguardando decisão."}
    if waiting[0]['tool'] == 'pedir_resposta':
        return {"speech": "Esta é uma pergunta aberta. Diga responder."}
    if d.approve:
        if not PIN or not hmac.compare_digest(d.pin.encode(), PIN.encode()):
            fails = lock["fails"] + 1
            if fails >= 3:
                store.set_pin_lock(0, time.time() + 300)
                return {"speech": "PIN incorreto três vezes. Aprovação por voz bloqueada por cinco minutos."}
            store.set_pin_lock(fails, lock["until"])
            return {"speech": "PIN incorreto."}
        store.set_pin_lock(0, 0.0)
    store.resolve_approval(waiting[0]["id"], "allow" if d.approve else "deny")
    return {"speech": "Aprovado. O agente vai continuar." if d.approve else "Negado. O agente foi informado."}


@app.get("/health")
def health():
    return {"ok": True}


app.include_router(_runs_router(supervisor, store, auth_control, PROJECTS_ROOT))
app.include_router(_dictation_router(dictation, auth_control))
app.include_router(_projects_router(project_creator, dictation, auth_control))
app.include_router(_activity_router(store, auth_control, PROJECTS_ROOT))

# /mcp: mesma app, credencial propria (Bearer ou x-secret). Montado por ultimo: rotas acima tem precedencia.
app.mount("/", mcp_mod.SecretAuth(_mcp_dispatch, SECRET))
