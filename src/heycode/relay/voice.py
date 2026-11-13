"""Porte dos tratadores de intent do Lambda do dono (skill/lambda/index.js) para o modo compartilhado.

Mesmas falas, mesmos reprompts, mesmos atributos de sessao e as mesmas chamadas a ponte. O relay nao guarda
estado de sessao: ele vive nos atributos da sessao da Alexa (entram em `session.attributes` e saem em
`sessionAttributes`). As chamadas a ponte passam por `call(method, path, body)`, que fala com o computador.
"""

import unicodedata
from collections.abc import Awaitable, Callable
from urllib.parse import quote

from heycode.relay.shortcuts import match

FAIL_SPEECH = "Não consegui falar com o seu computador. Verifique se o heycode connect está rodando."
FALLBACK_SPEECH = "Não entendi. Tente: qual o status?"
NEED_PENDING = "Pergunte primeiro o que está pendente."

Call = Callable[..., Awaitable[dict]]


class BridgeUnavailable(Exception):
    """Computador offline, sem resposta no prazo, cota estourada ou erro da ponte.

    `speech` opcional: fala especifica (offline, cota); sem ela vale a frase unica FAIL_SPEECH."""

    def __init__(self, message: str = "", speech: str | None = None) -> None:
        super().__init__(message)
        self.speech = speech


class Reply:
    def __init__(self, speech: str, reprompt: str | None = None, elicit: str | None = None) -> None:
        self.speech, self.reprompt, self.elicit = speech, reprompt, elicit

    def build(self, attrs: dict) -> dict:
        response: dict = {"outputSpeech": {"type": "PlainText", "text": self.speech}}
        open_session = bool(self.reprompt or self.elicit)
        if self.reprompt:
            response["reprompt"] = {"outputSpeech": {"type": "PlainText", "text": self.reprompt}}
        if self.elicit:
            response["directives"] = [{"type": "Dialog.ElicitSlot", "slotToElicit": self.elicit}]
        response["shouldEndSession"] = not open_session
        return {"version": "1.0", "sessionAttributes": attrs, "response": response}


def _norm(value: object) -> str:
    text = unicodedata.normalize("NFD", str(value or ""))
    return "".join(c for c in text if not unicodedata.combining(c)).lower().strip()


class _Req:
    def __init__(self, data: dict, shortcuts: list[dict] | None = None, meta: dict | None = None) -> None:
        self.shortcuts = shortcuts or []
        self.meta = meta if meta is not None else {}
        req = data.get("request") or {}
        self.type = req.get("type")
        intent = req.get("intent") or {}
        self.name = intent.get("name")
        self.slots = intent.get("slots") or {}
        self.attrs: dict = dict((data.get("session") or {}).get("attributes") or {})

    def slot(self, name: str) -> str:
        return str((self.slots.get(name) or {}).get("value") or "").strip()

    def resolved_id(self, name: str) -> str | None:
        slot = self.slots.get(name) or {}
        for auth in (slot.get("resolutions") or {}).get("resolutionsPerAuthority") or []:
            if (auth.get("status") or {}).get("code") == "ER_SUCCESS_MATCH":
                values = auth.get("values") or []
                if values:
                    return (values[0].get("value") or {}).get("id")
        return None


MODE_BY_TEXT = {
    "manual": "manual",
    "auto": "auto",
    "automatico": "auto",
    "tudo liberado": "auto",
    "decisoes": "decisoes",
    "decisao": "decisoes",
}
MODE_NAMES = {"manual": "manual", "auto": "automático", "decisoes": "decisões"}
OFF_WORDS = {"desligar", "desligado", "desliga", "desligue", "desativar", "desativa"}
AGENTS = ("claude", "codex", "aider")


def _resolve_mode(r: _Req) -> str | None:
    if not r.slot("modo"):
        return None
    ident = r.resolved_id("modo")
    if ident in ("manual", "auto", "decisoes"):
        return ident
    return MODE_BY_TEXT.get(_norm(r.slot("modo")))


def _resolve_agent(r: _Req) -> str | None:
    if not r.slot("agente"):
        return None
    ident = r.resolved_id("agente")
    if ident in AGENTS:
        return ident
    value = _norm(r.slot("agente"))
    return value if value in AGENTS else None


def _resolve_project(r: _Req) -> str | None:
    if not r.slot("projeto"):
        return None
    return r.resolved_id("projeto") or r.slot("projeto") or None


def _say(d: dict) -> str:
    text = d.get("speech")
    if not isinstance(text, str) or not text:
        raise BridgeUnavailable("resposta da ponte sem fala")
    return text


async def _list_projects(r: _Req, call: Call, offset: int) -> Reply:
    d = await call("GET", f"/voice/projects?offset={offset}")
    nxt = d.get("next_offset")
    if isinstance(nxt, int) and not isinstance(nxt, bool) and nxt >= 0:
        r.attrs["projects_next_offset"] = nxt
    else:
        r.attrs.pop("projects_next_offset", None)
    if nxt is not None:
        return Reply(_say(d), "Diga mais projetos, ou escolha um projeto.")
    if d.get("projects"):
        return Reply(_say(d), "Qual projeto quer escolher?")
    return Reply(_say(d))


async def _dictate(r: _Req, call: Call, agent: str, text: str, project: str | None) -> Reply:
    body = {"agent": agent, "text": text}
    if project:
        body["project"] = project
    d = await call("POST", "/dictation", body)
    if d.get("ok") is not False:
        r.attrs.pop("block_prior_confirmation", None)
        return Reply(_say(d), "Confirma?")
    return Reply(_say(d))


async def _launch(r: _Req, call: Call) -> Reply:
    return Reply("Pronto. Pergunte o status, se tem algo pendente, ou peça o resumo.", "Quer saber o status do agente?")


async def _status(r: _Req, call: Call) -> Reply:
    project = r.attrs.get("selected_project")
    d = await call("GET", f"/voice/projects/status?project={quote(project, safe='')}" if project else "/status")
    return Reply(_say(d), "Quer fazer algo nesse projeto?" if project else None)


async def _more_projects(r: _Req, call: Call) -> Reply:
    offset = r.attrs.get("projects_next_offset")
    if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
        return Reply("Não há mais projetos nessa lista. Você pode pedir os projetos ativos.", "O que deseja fazer?")
    return await _list_projects(r, call, offset)


async def _pending(r: _Req, call: Call) -> Reply:
    r.attrs.pop("pending_command", None)
    d = await call("GET", "/pending")
    # amarra a decisao ao pedido que foi lido em voz alta
    if d.get("approval_id") is None:
        r.attrs.pop("approval_id", None)
    else:
        r.attrs["approval_id"] = d["approval_id"]
    r.attrs["pending_kind"] = d.get("kind") or "approval"
    r.attrs.pop("free_answer", None)
    return Reply(_say(d), _action_reprompt(d))


def _action_reprompt(d: dict) -> str | None:
    if not d.get("actionable"):
        return None
    return "Diga responder." if d.get("kind") == "question" else "Diga aprovar com o seu PIN, ou negar."


async def _result(r: _Req, call: Call) -> Reply:
    d = await call("GET", "/result")
    return Reply(_say(d), _action_reprompt(d))


async def _approve(r: _Req, call: Call) -> Reply:
    if r.attrs.get("pending_command"):  # comando local que exige PIN: a ponte verifica o PIN (ADR 0053)
        pin = r.slot("pin")
        if not pin:
            return Reply("Qual é o seu PIN?", "Diga o seu PIN de quatro dígitos.", elicit="pin")
        d = await call("POST", "/voice/commands/confirm", {"pin": pin})
        if d.get("done"):
            r.attrs.pop("pending_command", None)
        return Reply(_say(d))
    approval_id = r.attrs.get("approval_id")
    if approval_id is None:
        return Reply(NEED_PENDING, "O que você quer saber?")
    pin = r.slot("pin")
    if not pin:
        return Reply("Qual é o seu PIN?", "Diga o seu PIN de quatro dígitos.", elicit="pin")
    d = await call("POST", "/decide", {"approve": True, "pin": pin, "approval_id": approval_id})
    return Reply(_say(d))


async def _deny(r: _Req, call: Call) -> Reply:
    if r.attrs.get("pending_command"):
        r.attrs.pop("pending_command", None)
        return Reply(_say(await call("POST", "/voice/commands/cancel")))
    approval_id = r.attrs.get("approval_id")
    if approval_id is None:
        return Reply(NEED_PENDING, "O que você quer saber?")
    d = await call("POST", "/decide", {"approve": False, "approval_id": approval_id})
    return Reply(_say(d))


async def _set_mode(r: _Req, call: Call) -> Reply:
    mode = _resolve_mode(r)
    if not mode:
        return Reply(
            "Não entendi o modo. Diga manual, automático ou decisões.", "Qual modo: manual, automático ou decisões?"
        )
    d = await call("POST", "/mode", {"mode": mode})
    name = MODE_NAMES.get(d.get("mode") or mode, mode)
    return Reply(d.get("speech") or f"Modo {name} ativado.")


async def _report_on_end(r: _Req, call: Call) -> Reply:
    on = _norm(r.slot("ligado")) not in OFF_WORDS
    d = await call("POST", "/mode", {"report_on_end": on})
    ligado = on if d.get("report_on_end") is None else d["report_on_end"]
    return Reply(d.get("speech") or f"Aviso de fim de ciclo {'ligado' if ligado else 'desligado'}.")


async def _select_project(r: _Req, call: Call) -> Reply:
    project = _resolve_project(r)
    if not project:
        return Reply("Qual projeto você quer escolher?", "Diga o nome do projeto.")
    d = await call("GET", f"/voice/projects/resolve?name={quote(project, safe='')}")
    # uma troca explicita nunca deixa resposta de outro fluxo pronta para confirmacao
    r.attrs.pop("free_answer", None)
    r.attrs.pop("pending_command", None)
    r.attrs.pop("ask", None)
    r.attrs["block_prior_confirmation"] = True
    if d.get("ok") and isinstance(d.get("project"), str) and d["project"]:
        r.attrs["selected_project"] = d["project"]
    else:
        r.attrs.pop("selected_project", None)
    return Reply(_say(d), "O que quer fazer?")


async def _answer_question(r: _Req, call: Call) -> Reply:
    if r.attrs.get("pending_kind") != "question" or r.attrs.get("approval_id") is None:
        return Reply(NEED_PENDING)
    text = r.slot("resposta")
    if not text:
        return Reply("Qual é a resposta?", "Qual é a resposta?", elicit="resposta")
    d = await call("POST", "/answer/preview", {"approval_id": r.attrs["approval_id"], "text": text})
    if d.get("ok"):
        r.attrs["free_answer"] = {"approval_id": r.attrs["approval_id"], "token": d.get("token")}
        return Reply(_say(d), "Confirma?")
    r.attrs.pop("free_answer", None)
    return Reply(_say(d))


async def _confirm_answer(r: _Req, call: Call) -> Reply:
    answer = r.attrs.pop("free_answer")
    d = await call("POST", "/answer/confirm", answer)
    return Reply(_say(d))


async def _cancel_answer(r: _Req, call: Call) -> Reply:
    r.attrs.pop("free_answer", None)
    return Reply("Resposta cancelada. A pergunta continua pendente.")


async def _ask_agent(r: _Req, call: Call) -> Reply:
    r.attrs.pop("free_answer", None)
    r.attrs.pop("pending_command", None)
    saved = r.attrs.get("ask") or {}
    agent = _resolve_agent(r) or saved.get("agent")
    project = _resolve_project(r) or saved.get("project") or r.attrs.get("selected_project")
    text = r.slot("instrucao")
    if not agent:
        return Reply(
            "Diga o agente primeiro. Por exemplo: peça ao claude. Depois eu pergunto a instrução.",
            "Para qual agente: claude, codex ou aider?",
        )
    if not text:
        r.attrs["ask"] = {"agent": agent, "project": project} if project else {"agent": agent}
        return Reply(f"Qual é a instrução para o {agent}?", "Qual é a instrução?", elicit="instrucao")
    r.attrs.pop("ask", None)
    return await _dictate(r, call, agent, text, project)


async def _send_instruction(r: _Req, call: Call) -> Reply:
    r.attrs.pop("free_answer", None)
    r.attrs.pop("pending_command", None)
    if r.attrs.get("selected_project"):
        return Reply(
            "Ainda não consigo avisar o agente aberto de um projeto específico. "
            "Você pode pedir uma nova tarefa ao agente nesse projeto.",
            "Qual tarefa deseja pedir?",
        )
    text = r.slot("instrucao")
    if not text:
        return Reply("Qual é a instrução para o agente aberto?", "O que devo avisar ao agente?")
    d = await call("POST", "/dictation", {"target": "aberto", "text": text})  # fila da sessao aberta (ADR 0018)
    if d.get("ok") is not False:
        r.attrs.pop("block_prior_confirmation", None)
        return Reply(_say(d), "Confirma?")
    return Reply(_say(d))


async def _create_project(r: _Req, call: Call) -> Reply:
    r.attrs.pop("free_answer", None)
    r.attrs.pop("pending_command", None)
    saved = r.attrs.get("create") or {}
    agent = _resolve_agent(r) or saved.get("agent")
    name = r.slot("nome") or saved.get("name") or ""
    description = r.slot("descricao")
    if not agent or not name:
        return Reply(
            "Diga o nome e o agente. Por exemplo: crie o projeto meu app com o claude. "
            "Depois eu pergunto para que ele serve.",
            "Qual o nome do projeto e o agente?",
        )
    if not description:
        r.attrs["create"] = {"name": name, "agent": agent}
        return Reply(f"Para que serve o projeto {name}?", "Para que serve o projeto?", elicit="descricao")
    r.attrs.pop("create", None)
    d = await call("POST", "/projects", {"name": name, "agent": agent, "description": description})
    if d.get("ok") is not False:
        r.attrs.pop("block_prior_confirmation", None)
        return Reply(_say(d), "Confirma?")
    return Reply(_say(d))


async def _run_command(r: _Req, call: Call) -> Reply:
    """Atalho cadastrado no painel: vira o mesmo ditado do pedido por voz, que pede "Confirma?" (ADR 0048)."""
    r.attrs.pop("free_answer", None)
    r.attrs.pop("pending_command", None)
    spoken = r.slot("comando")
    if not spoken:
        return Reply("Qual comando você quer executar?", "Qual comando?", elicit="comando")
    found, why = match(spoken, r.shortcuts) if r.shortcuts else (None, "none")
    if found is not None:  # atalho de agente cadastrado no painel (fase A)
        r.meta["label"] = found["name"]
        project = found.get("project") or r.attrs.get("selected_project")
        return await _dictate(r, call, found["agent"], found["instruction"], project)
    if why == "ambiguous":
        return Reply("Mais de um comando parece esse. Diga o nome completo.", "Qual comando?")
    # nenhum atalho: a maquina procura nos comandos locais (scripts e webhooks, ADR 0051)
    d = await call("POST", "/voice/commands/run", {"spoken": spoken})
    if d.get("label"):
        r.meta["label"] = d["label"]
    pending = d.get("pending")
    if isinstance(pending, dict) and pending.get("risk") in ("confirmar", "pin"):
        r.attrs["pending_command"] = {"risk": pending["risk"]}
        again = "Confirma?" if pending["risk"] == "confirmar" else "Diga aprovar com o seu PIN."
        return Reply(_say(d), again)
    return Reply(_say(d), None if d.get("ok") or d.get("label") else "Qual comando?")


async def _confirm_command(r: _Req, call: Call) -> Reply:
    if (r.attrs.get("pending_command") or {}).get("risk") == "pin":
        return Reply("Esse comando exige o seu PIN. Diga aprovar e o seu PIN.", "Diga aprovar e o seu PIN.")
    d = await call("POST", "/voice/commands/confirm", {})
    if d.get("done"):
        r.attrs.pop("pending_command", None)
    return Reply(_say(d))


async def _cancel_command(r: _Req, call: Call) -> Reply:
    r.attrs.pop("pending_command", None)
    return Reply(_say(await call("POST", "/voice/commands/cancel")))


def _simple_post(path: str) -> Callable[[_Req, Call], Awaitable[Reply]]:
    async def run(r: _Req, call: Call) -> Reply:
        return Reply(_say(await call("POST", path)))

    return run


async def _reject_stale(r: _Req, call: Call) -> Reply:
    return Reply("Escolha uma nova tarefa antes de confirmar.", "O que deseja fazer?")


async def _help(r: _Req, call: Call) -> Reply:
    return Reply(
        "Você pode listar projetos ativos, escolher um projeto, perguntar o status ou pedir uma tarefa a um agente.",
        "O que deseja saber?",
    )


async def _stop(r: _Req, call: Call) -> Reply:
    return Reply("Até já.")


async def _fallback(r: _Req, call: Call) -> Reply:
    return Reply(FALLBACK_SPEECH, "Qual o status?")


_BY_INTENT: dict[str, Callable[[_Req, Call], Awaitable[Reply]]] = {
    "StatusIntent": _status,
    "ListProjectsIntent": lambda r, c: _list_projects(r, c, 0),
    "MoreProjectsIntent": _more_projects,
    "SelectProjectIntent": _select_project,
    "PendingIntent": _pending,
    "ResultIntent": _result,
    "ApproveIntent": _approve,
    "DenyIntent": _deny,
    "SetModeIntent": _set_mode,
    "ReportOnEndIntent": _report_on_end,
    "AskAgentIntent": _ask_agent,
    "RunCommandIntent": _run_command,
    "SendInstructionIntent": _send_instruction,
    "AnswerQuestionIntent": _answer_question,
    "CancelRunIntent": _simple_post("/runs/latest/cancel"),
    "CreateProjectIntent": _create_project,
    "AMAZON.HelpIntent": _help,
    "AMAZON.StopIntent": _stop,
    "AMAZON.CancelIntent": _stop,
    "AMAZON.FallbackIntent": _fallback,
}


def _pick(r: _Req) -> Callable[[_Req, Call], Awaitable[Reply]]:
    if r.type == "LaunchRequest":
        return _launch
    if r.type != "IntentRequest":
        return _fallback
    if r.name == "ConfirmIntent":  # a ordem importa, como no Lambda
        if r.attrs.get("free_answer"):
            return _confirm_answer
        if r.attrs.get("pending_command"):
            return _confirm_command
        if r.attrs.get("block_prior_confirmation"):
            return _reject_stale
        return _simple_post("/confirm")
    if r.name == "CancelDictationIntent":
        if r.attrs.get("free_answer"):
            return _cancel_answer
        return _cancel_command if r.attrs.get("pending_command") else _simple_post("/cancel")
    return _BY_INTENT.get(r.name or "", _fallback)


async def handle(data: dict, call: Call, *, shortcuts: list[dict] | None = None, meta: dict | None = None) -> dict:
    """Resposta da Alexa para a requisicao ja verificada. Nunca levanta: falha da ponte vira FAIL_SPEECH.

    `shortcuts`: atalhos da conta; `meta`: recebe {"label": nome} do atalho usado (para o rastro)."""
    r = _Req(data, shortcuts, meta)
    if r.type == "SessionEndedRequest":
        return {"version": "1.0", "response": {}}
    try:
        reply = await _pick(r)(r, call)
    except BridgeUnavailable as exc:
        return Reply(exc.speech or FAIL_SPEECH).build(r.attrs)
    return reply.build(r.attrs)
