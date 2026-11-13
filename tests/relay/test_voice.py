"""Equivalencia com skill/lambda/index.js: mesmas falas, mesmos atributos de sessao, mesmas chamadas a ponte."""

import asyncio

import pytest

from heycode.relay.voice import FAIL_SPEECH, BridgeUnavailable, handle


class Bridge:
    """Ponte falsa: devolve o que foi programado por (metodo, caminho) e guarda as chamadas."""

    def __init__(self, replies=None):
        self.replies = replies or {}
        self.calls = []

    async def __call__(self, method, path, body=None):
        self.calls.append((method, path, body))
        reply = self.replies.get((method, path))
        if isinstance(reply, Exception):
            raise reply
        return reply if reply is not None else {"speech": "ok"}


def intent(name, slots=None, attrs=None):
    s = {k: {"name": k, "value": v} for k, v in (slots or {}).items()}
    return {
        "session": {"attributes": dict(attrs or {})},
        "request": {"type": "IntentRequest", "intent": {"name": name, "slots": s}},
    }


def run(req, bridge):
    return asyncio.run(handle(req, bridge))


def speech(r):
    return r["response"]["outputSpeech"]["text"]


def reprompt(r):
    return (r["response"].get("reprompt") or {}).get("outputSpeech", {}).get("text")


def elicit(r):
    return [d["slotToElicit"] for d in r["response"].get("directives", []) if d["type"] == "Dialog.ElicitSlot"]


def attrs_of(r):
    return r.get("sessionAttributes", {})


def test_abertura_usa_a_fala_do_lambda():
    r = run({"request": {"type": "LaunchRequest"}}, Bridge())
    assert speech(r) == "Pronto. Pergunte o status, se tem algo pendente, ou peça o resumo."
    assert reprompt(r) == "Quer saber o status do agente?" and r["response"]["shouldEndSession"] is False


def test_status_sem_projeto_chama_status_e_sem_reprompt():
    b = Bridge({("GET", "/status"): {"speech": "Tudo parado."}})
    r = run(intent("StatusIntent"), b)
    assert b.calls == [("GET", "/status", None)] and speech(r) == "Tudo parado."
    assert reprompt(r) is None and r["response"]["shouldEndSession"] is True


def test_status_com_projeto_selecionado_consulta_o_projeto_e_pergunta():
    b = Bridge({("GET", "/voice/projects/status?project=meu%20app"): {"speech": "Rodando."}})
    r = run(intent("StatusIntent", attrs={"selected_project": "meu app"}), b)
    assert speech(r) == "Rodando." and reprompt(r) == "Quer fazer algo nesse projeto?"


def test_lista_de_projetos_guarda_o_proximo_offset_e_pergunta():
    b = Bridge({("GET", "/voice/projects?offset=0"): {"speech": "A, B.", "projects": ["a", "b"], "next_offset": 2}})
    r = run(intent("ListProjectsIntent"), b)
    assert attrs_of(r)["projects_next_offset"] == 2
    assert reprompt(r) == "Diga mais projetos, ou escolha um projeto."


def test_lista_sem_proxima_pagina_pergunta_qual_escolher_e_limpa_o_offset():
    b = Bridge({("GET", "/voice/projects?offset=0"): {"speech": "A.", "projects": ["a"], "next_offset": None}})
    r = run(intent("ListProjectsIntent", attrs={"projects_next_offset": 9}), b)
    assert "projects_next_offset" not in attrs_of(r) and reprompt(r) == "Qual projeto quer escolher?"


def test_lista_vazia_nao_tem_reprompt():
    b = Bridge({("GET", "/voice/projects?offset=0"): {"speech": "Nenhum.", "projects": []}})
    assert reprompt(run(intent("ListProjectsIntent"), b)) is None


def test_mais_projetos_usa_o_offset_da_sessao_e_sem_offset_explica():
    b = Bridge({("GET", "/voice/projects?offset=2"): {"speech": "C.", "projects": ["c"]}})
    run(intent("MoreProjectsIntent", attrs={"projects_next_offset": 2}), b)
    assert b.calls[0][1] == "/voice/projects?offset=2"
    b2 = Bridge()
    r = run(intent("MoreProjectsIntent"), b2)
    assert b2.calls == [] and speech(r) == "Não há mais projetos nessa lista. Você pode pedir os projetos ativos."


def test_pendencia_amarra_a_decisao_ao_pedido_lido_em_voz_alta():
    b = Bridge(
        {("GET", "/pending"): {"speech": "Quer rodar ls.", "approval_id": 7, "kind": "approval", "actionable": True}}
    )
    r = run(intent("PendingIntent", attrs={"free_answer": {"x": 1}}), b)
    a = attrs_of(r)
    assert a["approval_id"] == 7 and a["pending_kind"] == "approval" and "free_answer" not in a
    assert reprompt(r) == "Diga aprovar com o seu PIN, ou negar."


def test_pendencia_do_tipo_pergunta_pede_para_responder():
    b = Bridge(
        {("GET", "/pending"): {"speech": "Qual banco?", "approval_id": 3, "kind": "question", "actionable": True}}
    )
    r = run(intent("PendingIntent"), b)
    assert attrs_of(r)["pending_kind"] == "question" and reprompt(r) == "Diga responder."


def test_sem_pendencia_remove_o_approval_id_da_sessao():
    b = Bridge({("GET", "/pending"): {"speech": "Nada pendente.", "approval_id": None}})
    r = run(intent("PendingIntent", attrs={"approval_id": 5}), b)
    assert "approval_id" not in attrs_of(r) and attrs_of(r)["pending_kind"] == "approval" and reprompt(r) is None


def test_resultado_repete_o_reprompt_de_acao_mas_nao_mexe_na_sessao():
    b = Bridge({("GET", "/result"): {"speech": "Terminou.", "actionable": True, "kind": "approval"}})
    r = run(intent("ResultIntent", attrs={"approval_id": 5}), b)
    assert attrs_of(r) == {"approval_id": 5} and reprompt(r) == "Diga aprovar com o seu PIN, ou negar."


def test_aprovar_sem_pendencia_lida_manda_perguntar_primeiro():
    b = Bridge()
    r = run(intent("ApproveIntent", {"pin": "1234"}), b)
    assert speech(r) == "Pergunte primeiro o que está pendente." and reprompt(r) == "O que você quer saber?"
    assert b.calls == []


def test_aprovar_sem_pin_pede_o_pin_com_elicit():
    r = run(intent("ApproveIntent", attrs={"approval_id": 7}), Bridge())
    assert speech(r) == "Qual é o seu PIN?" and elicit(r) == ["pin"]
    assert reprompt(r) == "Diga o seu PIN de quatro dígitos."


def test_aprovar_com_pin_envia_a_decisao_atada_ao_pedido():
    b = Bridge({("POST", "/decide"): {"speech": "Aprovado."}})
    r = run(intent("ApproveIntent", {"pin": "1234"}, {"approval_id": 7}), b)
    assert b.calls == [("POST", "/decide", {"approve": True, "pin": "1234", "approval_id": 7})]
    assert speech(r) == "Aprovado."


def test_negar_nao_envia_pin():
    b = Bridge({("POST", "/decide"): {"speech": "Negado."}})
    run(intent("DenyIntent", attrs={"approval_id": 7}), b)
    assert b.calls == [("POST", "/decide", {"approve": False, "approval_id": 7})]
    assert speech(run(intent("DenyIntent"), Bridge())) == "Pergunte primeiro o que está pendente."


def test_modo_resolve_por_id_do_slot_e_por_texto():
    b = Bridge({("POST", "/mode"): {"speech": "Modo manual ativado.", "mode": "manual"}})
    run(intent("SetModeIntent", {"modo": "tudo liberado"}), b)
    assert b.calls[0][2] == {"mode": "auto"}
    b = Bridge()
    run(intent("SetModeIntent", {"modo": "Decisões"}), b)
    assert b.calls[0][2] == {"mode": "decisoes"}
    req = intent("SetModeIntent", {"modo": "qualquer"})
    req["request"]["intent"]["slots"]["modo"]["resolutions"] = {
        "resolutionsPerAuthority": [{"status": {"code": "ER_SUCCESS_MATCH"}, "values": [{"value": {"id": "manual"}}]}]
    }
    b = Bridge()
    run(req, b)
    assert b.calls[0][2] == {"mode": "manual"}


def test_modo_nao_entendido_pergunta_de_novo_sem_chamar_a_ponte():
    b = Bridge()
    r = run(intent("SetModeIntent", {"modo": "xpto"}), b)
    assert b.calls == [] and speech(r) == "Não entendi o modo. Diga manual, automático ou decisões."
    assert reprompt(r) == "Qual modo: manual, automático ou decisões?"


def test_modo_sem_fala_da_ponte_usa_a_fala_padrao():
    r = run(intent("SetModeIntent", {"modo": "manual"}), Bridge({("POST", "/mode"): {"mode": "manual"}}))
    assert speech(r) == "Modo manual ativado."


def test_auto_barrado_no_computador_fala_a_explicacao_da_ponte():
    b = Bridge({("POST", "/mode"): {"error": "auto_not_allowed", "speech": "Primeiro ligue no computador."}})
    assert speech(run(intent("SetModeIntent", {"modo": "automatico"}), b)) == "Primeiro ligue no computador."


def test_aviso_de_fim_de_ciclo_liga_e_desliga():
    b = Bridge({("POST", "/mode"): {}})
    r = run(intent("ReportOnEndIntent", {"ligado": "ligar"}), b)
    assert b.calls[0][2] == {"report_on_end": True} and speech(r) == "Aviso de fim de ciclo ligado."
    b = Bridge({("POST", "/mode"): {}})
    r = run(intent("ReportOnEndIntent", {"ligado": "Desligar"}), b)
    assert b.calls[0][2] == {"report_on_end": False} and speech(r) == "Aviso de fim de ciclo desligado."


def test_selecionar_projeto_guarda_na_sessao_e_bloqueia_confirmacao_antiga():
    b = Bridge(
        {("GET", "/voice/projects/resolve?name=meu%20app"): {"ok": True, "project": "meu-app", "speech": "Escolhi."}}
    )
    r = run(
        intent("SelectProjectIntent", {"projeto": "meu app"}, {"free_answer": {"x": 1}, "ask": {"agent": "claude"}}), b
    )
    a = attrs_of(r)
    assert a["selected_project"] == "meu-app" and a["block_prior_confirmation"] is True
    assert "free_answer" not in a and "ask" not in a and reprompt(r) == "O que quer fazer?"


def test_selecionar_projeto_nao_encontrado_limpa_a_selecao():
    b = Bridge({("GET", "/voice/projects/resolve?name=x"): {"ok": False, "speech": "Nao achei."}})
    r = run(intent("SelectProjectIntent", {"projeto": "x"}, {"selected_project": "antigo"}), b)
    assert "selected_project" not in attrs_of(r)


def test_selecionar_projeto_sem_nome_pergunta():
    r = run(intent("SelectProjectIntent"), Bridge())
    assert speech(r) == "Qual projeto você quer escolher?" and reprompt(r) == "Diga o nome do projeto."


def test_pedir_ao_agente_sem_agente_ensina_a_frase():
    r = run(intent("AskAgentIntent"), Bridge())
    assert (
        speech(r).startswith("Diga o agente primeiro.") and reprompt(r) == "Para qual agente: claude, codex ou aider?"
    )


def test_pedir_ao_agente_sem_instrucao_guarda_o_destino_e_pergunta():
    r = run(intent("AskAgentIntent", {"agente": "codex", "projeto": "api"}), Bridge())
    assert attrs_of(r)["ask"] == {"agent": "codex", "project": "api"}
    assert speech(r) == "Qual é a instrução para o codex?" and elicit(r) == ["instrucao"]


def test_segundo_turno_usa_o_destino_guardado_e_ditado_pede_confirmacao():
    b = Bridge({("POST", "/dictation"): {"speech": "Vou pedir ao codex. Confirma?", "ok": True}})
    r = run(
        intent(
            "AskAgentIntent",
            {"instrucao": "corrija o login"},
            {"ask": {"agent": "codex", "project": "api"}, "block_prior_confirmation": True},
        ),
        b,
    )
    assert b.calls == [("POST", "/dictation", {"agent": "codex", "text": "corrija o login", "project": "api"})]
    a = attrs_of(r)
    assert "ask" not in a and "block_prior_confirmation" not in a and reprompt(r) == "Confirma?"


def test_ditado_recusado_pela_ponte_nao_pede_confirmacao():
    b = Bridge({("POST", "/dictation"): {"speech": "Ja existe uma pendente.", "ok": False}})
    r = run(intent("AskAgentIntent", {"agente": "claude", "instrucao": "x"}), b)
    assert reprompt(r) is None


def test_pedir_usa_o_projeto_selecionado_quando_nao_ha_outro():
    b = Bridge()
    run(intent("AskAgentIntent", {"agente": "claude", "instrucao": "x"}, {"selected_project": "api"}), b)
    assert b.calls[0][2]["project"] == "api"


def test_instrucao_ao_agente_aberto_vai_com_target_aberto():
    b = Bridge({("POST", "/dictation"): {"speech": "Confirma?", "ok": True}})
    r = run(intent("SendInstructionIntent", {"instrucao": "pare"}), b)
    assert b.calls == [("POST", "/dictation", {"target": "aberto", "text": "pare"})] and reprompt(r) == "Confirma?"


def test_instrucao_ao_aberto_com_projeto_selecionado_e_recusada():
    b = Bridge()
    r = run(intent("SendInstructionIntent", {"instrucao": "x"}, {"selected_project": "api"}), b)
    assert b.calls == [] and speech(r).startswith("Ainda não consigo avisar o agente aberto")
    r = run(intent("SendInstructionIntent"), Bridge())
    assert speech(r) == "Qual é a instrução para o agente aberto?"


def test_resposta_livre_so_vale_para_pergunta_pendente():
    assert (
        speech(run(intent("AnswerQuestionIntent", {"resposta": "sim"}), Bridge()))
        == "Pergunte primeiro o que está pendente."
    )
    a = {"pending_kind": "question", "approval_id": 3}
    r = run(intent("AnswerQuestionIntent", attrs=a), Bridge())
    assert speech(r) == "Qual é a resposta?" and elicit(r) == ["resposta"]


def test_resposta_livre_gera_previa_e_so_confirma_com_o_token():
    a = {"pending_kind": "question", "approval_id": 3}
    b = Bridge({("POST", "/answer/preview"): {"ok": True, "token": "tk", "speech": "Vou responder sim. Confirma?"}})
    r = run(intent("AnswerQuestionIntent", {"resposta": " sim "}, a), b)
    assert b.calls == [("POST", "/answer/preview", {"approval_id": 3, "text": "sim"})]
    assert attrs_of(r)["free_answer"] == {"approval_id": 3, "token": "tk"} and reprompt(r) == "Confirma?"
    b2 = Bridge({("POST", "/answer/confirm"): {"speech": "Enviado."}})
    r2 = run(intent("ConfirmIntent", attrs=attrs_of(r)), b2)
    assert b2.calls == [("POST", "/answer/confirm", {"approval_id": 3, "token": "tk"})]
    assert "free_answer" not in attrs_of(r2) and speech(r2) == "Enviado."


def test_cancelar_resposta_livre_nao_cancela_o_ditado():
    b = Bridge()
    r = run(intent("CancelDictationIntent", attrs={"free_answer": {"approval_id": 3, "token": "t"}}), b)
    assert b.calls == [] and "free_answer" not in attrs_of(r)
    assert speech(r) == "Resposta cancelada. A pergunta continua pendente."


def test_confirmacao_antiga_e_rejeitada_depois_de_trocar_de_projeto():
    b = Bridge()
    r = run(intent("ConfirmIntent", attrs={"block_prior_confirmation": True}), b)
    assert b.calls == [] and speech(r) == "Escolha uma nova tarefa antes de confirmar."


def test_confirmar_e_cancelar_ditado_simples():
    b = Bridge({("POST", "/confirm"): {"speech": "Feito."}, ("POST", "/cancel"): {"speech": "Cancelado."}})
    assert speech(run(intent("ConfirmIntent"), b)) == "Feito."
    assert speech(run(intent("CancelDictationIntent"), b)) == "Cancelado."
    assert [c[1] for c in b.calls] == ["/confirm", "/cancel"]


def test_cancelar_execucao():
    b = Bridge({("POST", "/runs/latest/cancel"): {"speech": "Cancelei."}})
    assert speech(run(intent("CancelRunIntent"), b)) == "Cancelei."


def test_criar_projeto_em_dois_turnos():
    r = run(intent("CreateProjectIntent"), Bridge())
    assert speech(r).startswith("Diga o nome e o agente.")
    r = run(intent("CreateProjectIntent", {"nome": "meu app", "agente": "claude"}), Bridge())
    assert attrs_of(r)["create"] == {"name": "meu app", "agent": "claude"}
    assert speech(r) == "Para que serve o projeto meu app?" and elicit(r) == ["descricao"]
    b = Bridge({("POST", "/projects"): {"speech": "Confirma?", "ok": True}})
    r = run(intent("CreateProjectIntent", {"descricao": "um app de notas"}, attrs_of(r)), b)
    assert b.calls == [("POST", "/projects", {"name": "meu app", "agent": "claude", "description": "um app de notas"})]
    assert "create" not in attrs_of(r) and reprompt(r) == "Confirma?"


def test_ajuda_parar_e_fallback():
    assert speech(run(intent("AMAZON.HelpIntent"), Bridge())).startswith("Você pode listar projetos ativos")
    for name in ("AMAZON.StopIntent", "AMAZON.CancelIntent"):
        r = run(intent(name), Bridge())
        assert speech(r) == "Até já." and r["response"]["shouldEndSession"] is True
    r = run(intent("AMAZON.FallbackIntent"), Bridge())
    assert speech(r) == "Não entendi. Tente: qual o status?" and reprompt(r) == "Qual o status?"


def test_intent_desconhecida_responde_como_fallback_sem_chamar_a_ponte():
    b = Bridge()
    r = run(intent("IntentQueNaoExiste"), b)
    assert b.calls == [] and speech(r) == "Não entendi. Tente: qual o status?"


def test_ponte_indisponivel_fala_a_frase_unica_e_acionavel():
    for name in ("StatusIntent", "PendingIntent", "ConfirmIntent", "SetModeIntent"):
        r = run(
            intent(name, {"modo": "manual"}),
            Bridge(
                {
                    (m, p): BridgeUnavailable()
                    for m in ("GET", "POST")
                    for p in ("/status", "/pending", "/confirm", "/mode")
                }
            ),
        )
        assert speech(r) == FAIL_SPEECH
    assert "heycode connect" in FAIL_SPEECH


def test_resposta_da_ponte_sem_fala_vira_a_frase_de_falha():
    assert speech(run(intent("StatusIntent"), Bridge({("GET", "/status"): {"nada": 1}}))) == FAIL_SPEECH


def test_sessao_e_devolvida_sempre_e_nunca_vaza_o_pin():
    b = Bridge({("POST", "/decide"): {"speech": "Aprovado."}})
    r = run(intent("ApproveIntent", {"pin": "4321"}, {"approval_id": 1, "selected_project": "api"}), b)
    assert attrs_of(r)["selected_project"] == "api"
    assert "4321" not in str(r)


@pytest.mark.parametrize("rtype", ["SessionEndedRequest"])
def test_fim_de_sessao_responde_vazio(rtype):
    r = run({"request": {"type": rtype}}, Bridge())
    assert r["response"] == {}
