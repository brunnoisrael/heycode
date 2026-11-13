import asyncio

import pytest
from conftest import Clock, signup
from fastapi.testclient import TestClient

from heycode.relay.app import create_app
from heycode.relay.repo import SqliteRepository
from heycode.relay.shortcuts import match, normalize
from heycode.relay.voice import handle

# ---------- normalizacao e casamento ----------


def sc(name, aliases=(), enabled=True, sid=None):
    return {
        "id": sid or name,
        "name": name,
        "aliases": list(aliases),
        "enabled": enabled,
        "agent": "claude",
        "project": None,
        "instruction": "faca",
    }


def test_normaliza_acento_caixa_pontuacao_e_artigos():
    assert normalize("  O Comando: Rodar os TESTES! ") == "rodar os testes"
    assert normalize("Atalho  Ação-Rápida") == "acao rapida"
    assert normalize("") == ""


def test_casa_nome_exato_e_apelido():
    lista = [sc("rodar testes", ["testar tudo"]), sc("subir deploy")]
    assert match("Rodar os testes", lista)[0]["name"] == "rodar testes"
    assert match("testar tudo", lista)[0]["name"] == "rodar testes"
    assert match("subir deploy", lista)[0]["name"] == "subir deploy"


def test_casa_por_semelhanca_quando_a_alexa_erra_uma_letra():
    lista = [sc("rodar testes"), sc("subir deploy")]
    assert match("rodar teste", lista)[0]["name"] == "rodar testes"
    assert match("sobir deploy", lista)[0]["name"] == "subir deploy"


def test_nao_acha_quando_nada_se_parece():
    assert match("fazer cafe", [sc("rodar testes")]) == (None, "none")
    assert match("", [sc("rodar testes")]) == (None, "none")
    assert match("rodar testes", []) == (None, "none")


def test_empate_e_recusado():
    lista = [sc("rodar testes api", sid="a"), sc("rodar testes app", sid="b")]
    assert match("rodar testes ap", lista) == (None, "ambiguous")


def test_comando_desligado_nunca_casa():
    assert match("rodar testes", [sc("rodar testes", enabled=False)]) == (None, "none")


def test_nome_exato_vence_semelhante():
    lista = [sc("rodar testes", sid="a"), sc("rodar teste rapido", sid="b")]
    assert match("rodar testes", lista)[0]["id"] == "a"


# ---------- voz: RunCommandIntent ----------


class Bridge:
    def __init__(self, replies=None):
        self.replies, self.calls = replies or {}, []

    async def __call__(self, method, path, body=None):
        self.calls.append((method, path, body))
        return self.replies.get((method, path), {"speech": "ok"})


def intent(slots=None, attrs=None):
    s = {k: {"name": k, "value": v} for k, v in (slots or {}).items()}
    return {
        "session": {"attributes": dict(attrs or {})},
        "request": {"type": "IntentRequest", "intent": {"name": "RunCommandIntent", "slots": s}},
    }


def run(req, bridge, shortcuts, meta=None):
    return asyncio.run(handle(req, bridge, shortcuts=shortcuts, meta=meta))


def speech(r):
    return r["response"]["outputSpeech"]["text"]


def test_atalho_vira_ditado_com_confirmacao_e_nao_executa_sozinho():
    b = Bridge({("POST", "/dictation"): {"speech": "Vou pedir ao codex. Confirma?", "ok": True}})
    lista = [{**sc("rodar testes"), "agent": "codex", "project": "api", "instruction": "rode os testes"}]
    meta = {}
    r = run(intent({"comando": "rodar os testes"}), b, lista, meta)
    assert b.calls == [("POST", "/dictation", {"agent": "codex", "text": "rode os testes", "project": "api"})]
    assert r["response"]["reprompt"]["outputSpeech"]["text"] == "Confirma?"
    assert [c[1] for c in b.calls] == ["/dictation"]  # nada alem do ditado: a execucao espera o "Confirma?"
    assert meta == {"label": "rodar testes"}


def test_atalho_sem_projeto_usa_o_projeto_da_sessao():
    b = Bridge()
    run(intent({"comando": "rodar testes"}, {"selected_project": "web"}), b, [sc("rodar testes")])
    assert b.calls[0][2]["project"] == "web"


def test_atalho_ambiguo_e_sem_nome_nao_chamam_o_computador():
    b = Bridge()
    amb = [sc("rodar testes api", sid="a"), sc("rodar testes app", sid="b")]
    assert "Mais de um" in speech(run(intent({"comando": "rodar testes ap"}), b, amb))
    r = run(intent(), b, [sc("rodar testes")])
    assert speech(r) == "Qual comando você quer executar?"
    assert r["response"]["directives"][0]["slotToElicit"] == "comando"
    assert b.calls == []


def test_sem_atalho_correspondente_a_fala_vai_para_os_comandos_locais():
    nao = {"ok": False, "speech": "Não achei esse comando. Diga executar e o nome de um comando cadastrado."}
    b = Bridge({("POST", "/voice/commands/run"): nao})
    assert "Não achei" in speech(run(intent({"comando": "cafe"}), b, [sc("rodar testes")]))
    assert b.calls == [("POST", "/voice/commands/run", {"spoken": "cafe"})]
    b2 = Bridge({("POST", "/voice/commands/run"): nao})
    assert "Não achei" in speech(run(intent({"comando": "x"}), b2, []))  # sem atalhos: direto aos locais
    assert len(b2.calls) == 1


def test_confirmacao_antiga_nao_e_herdada_pelo_atalho():
    b = Bridge({("POST", "/dictation"): {"speech": "Confirma?", "ok": True}})
    r = run(intent({"comando": "rodar testes"}, {"block_prior_confirmation": True}), b, [sc("rodar testes")])
    assert "block_prior_confirmation" not in r["sessionAttributes"]


# ---------- voz: comandos locais (scripts e webhooks) ----------


def local(replies):
    return Bridge({("POST", "/voice/commands/run"): replies} if isinstance(replies, dict) else replies)


def test_leitura_local_roda_e_fala_o_resultado_sem_pendencia():
    b = local({"ok": True, "label": "ver disco", "speech": "ver disco terminou com sucesso. Saída: 40 por cento."})
    meta = {}
    r = run(intent({"comando": "ver disco"}), b, [], meta)
    assert speech(r) == "ver disco terminou com sucesso. Saída: 40 por cento." and meta == {"label": "ver disco"}
    assert "pending_command" not in r["sessionAttributes"] and "reprompt" not in r["response"]


def test_confirmar_local_guarda_a_pendencia_e_pergunta():
    b = local(
        {
            "ok": True,
            "label": "reiniciar app",
            "pending": {"risk": "confirmar"},
            "speech": "Vou executar reiniciar app. Confirma?",
        }
    )
    r = run(intent({"comando": "reiniciar app"}), b, [])
    assert r["sessionAttributes"]["pending_command"] == {"risk": "confirmar"}
    assert r["response"]["reprompt"]["outputSpeech"]["text"] == "Confirma?"


def test_pin_local_pede_para_aprovar_com_o_pin():
    b = local(
        {
            "ok": True,
            "label": "deploy",
            "pending": {"risk": "pin"},
            "speech": "Vou executar deploy. Esse comando exige o seu PIN.",
        }
    )
    r = run(intent({"comando": "deploy"}), b, [])
    assert r["sessionAttributes"]["pending_command"] == {"risk": "pin"}
    assert "PIN" in r["response"]["reprompt"]["outputSpeech"]["text"]


def confirm_intent(attrs):
    return {
        "session": {"attributes": attrs},
        "request": {"type": "IntentRequest", "intent": {"name": "ConfirmIntent", "slots": {}}},
    }


def test_confirma_executa_o_comando_local_e_limpa_a_pendencia():
    b = Bridge(
        {
            ("POST", "/voice/commands/confirm"): {
                "ok": True,
                "done": True,
                "speech": "reiniciar app terminou com sucesso.",
            }
        }
    )
    r = run(confirm_intent({"pending_command": {"risk": "confirmar"}}), b, [])
    assert b.calls == [("POST", "/voice/commands/confirm", {})]
    assert speech(r) == "reiniciar app terminou com sucesso." and "pending_command" not in r["sessionAttributes"]


def test_confirma_nao_executa_comando_que_exige_pin():
    b = Bridge()
    r = run(confirm_intent({"pending_command": {"risk": "pin"}}), b, [])
    assert b.calls == [] and "PIN" in speech(r) and r["sessionAttributes"]["pending_command"] == {"risk": "pin"}


def test_pendencia_nao_cumprida_continua_ate_dar_certo():
    b = Bridge(
        {("POST", "/voice/commands/confirm"): {"ok": False, "done": False, "speech": "Já há um comando em execução."}}
    )
    r = run(confirm_intent({"pending_command": {"risk": "confirmar"}}), b, [])
    assert r["sessionAttributes"]["pending_command"] == {"risk": "confirmar"}


def approve(slots, attrs):
    s = {k: {"name": k, "value": v} for k, v in slots.items()}
    return {
        "session": {"attributes": attrs},
        "request": {"type": "IntentRequest", "intent": {"name": "ApproveIntent", "slots": s}},
    }


def test_aprovar_com_pin_executa_o_comando_local():
    b = Bridge(
        {("POST", "/voice/commands/confirm"): {"ok": True, "done": True, "speech": "deploy terminou com sucesso."}}
    )
    r = run(approve({"pin": "1234"}, {"pending_command": {"risk": "pin"}}), b, [])
    assert b.calls == [("POST", "/voice/commands/confirm", {"pin": "1234"})]
    assert speech(r) == "deploy terminou com sucesso." and "pending_command" not in r["sessionAttributes"]
    assert "1234" not in str(r)


def test_aprovar_sem_pin_pergunta_o_pin_e_pin_errado_mantem_a_pendencia():
    r = run(approve({}, {"pending_command": {"risk": "pin"}}), Bridge(), [])
    assert speech(r) == "Qual é o seu PIN?" and r["response"]["directives"][0]["slotToElicit"] == "pin"
    b = Bridge({("POST", "/voice/commands/confirm"): {"ok": False, "done": False, "speech": "PIN incorreto."}})
    r = run(approve({"pin": "0000"}, {"pending_command": {"risk": "pin"}}), b, [])
    assert speech(r) == "PIN incorreto." and r["sessionAttributes"]["pending_command"] == {"risk": "pin"}


def test_negar_e_cancelar_descartam_o_comando_local():
    b = Bridge({("POST", "/voice/commands/cancel"): {"ok": True, "speech": "Cancelado."}})
    deny = {
        "session": {"attributes": {"pending_command": {"risk": "confirmar"}}},
        "request": {"type": "IntentRequest", "intent": {"name": "DenyIntent", "slots": {}}},
    }
    r = run(deny, b, [])
    assert b.calls == [("POST", "/voice/commands/cancel", None)] and "pending_command" not in r["sessionAttributes"]
    cancel = {
        "session": {"attributes": {"pending_command": {"risk": "confirmar"}}},
        "request": {"type": "IntentRequest", "intent": {"name": "CancelDictationIntent", "slots": {}}},
    }
    b2 = Bridge({("POST", "/voice/commands/cancel"): {"ok": True, "speech": "Cancelado."}})
    r2 = run(cancel, b2, [])
    assert speech(r2) == "Cancelado." and "pending_command" not in r2["sessionAttributes"]


@pytest.mark.parametrize(
    "name", ["PendingIntent", "SelectProjectIntent", "AskAgentIntent", "SendInstructionIntent", "CreateProjectIntent"]
)
def test_nova_tarefa_descarta_a_pendencia_de_comando_local(name):
    slots = {
        "projeto": {"name": "projeto", "value": "api"},
        "agente": {"name": "agente", "value": "claude"},
        "instrucao": {"name": "instrucao", "value": "x"},
        "nome": {"name": "nome", "value": "meu app"},
    }
    req = {
        "session": {"attributes": {"pending_command": {"risk": "confirmar"}}},
        "request": {"type": "IntentRequest", "intent": {"name": name, "slots": slots}},
    }
    b = Bridge(
        {
            ("GET", "/pending"): {"speech": "Nada pendente."},
            ("GET", "/voice/projects/resolve?name=api"): {"ok": True, "project": "api", "speech": "ok"},
        }
    )
    r = run(req, b, [])
    assert "pending_command" not in r["sessionAttributes"]


# ---------- API do painel ----------


@pytest.fixture
def client():
    with TestClient(create_app(SqliteRepository(":memory:"), Clock())) as c:
        yield c


BODY = {
    "name": "Rodar testes",
    "aliases": ["testar tudo"],
    "agent": "codex",
    "project": "api",
    "instruction": "rode a suite de testes e resuma as falhas",
    "description": "roda a suite",
}


def test_crud_do_atalho(client):
    auth = signup(client, "a@exemplo.com")
    created = client.post("/v1/commands", headers=auth, json=BODY)
    assert created.status_code == 201
    item = created.json()
    assert item["name"] == "Rodar testes" and item["enabled"] is True and item["aliases"] == ["testar tudo"]
    assert client.get("/v1/commands", headers=auth).json() == [item]
    upd = client.put(f"/v1/commands/{item['id']}", headers=auth, json={**BODY, "enabled": False})
    assert upd.status_code == 200 and upd.json()["enabled"] is False
    assert client.delete(f"/v1/commands/{item['id']}", headers=auth).status_code == 204
    assert client.get("/v1/commands", headers=auth).json() == []


@pytest.mark.parametrize(
    "patch",
    [
        {"name": "a"},
        {"name": "x" * 41},
        {"agent": "gemini"},
        {"instruction": ""},
        {"instruction": "x" * 501},
        {"aliases": ["a"]},
        {"aliases": ["ok1", "ok2", "ok3", "ok4", "ok5", "ok6"]},
        {"project": "p" * 81},
        {"name": "  !!  "},
    ],
)
def test_validacao_recusa_entrada_ruim(client, patch):
    auth = signup(client, "a@exemplo.com")
    assert client.post("/v1/commands", headers=auth, json={**BODY, **patch}).status_code == 422


def test_nome_ou_apelido_repetido_na_conta_e_409(client):
    auth = signup(client, "a@exemplo.com")
    client.post("/v1/commands", headers=auth, json=BODY)
    assert client.post("/v1/commands", headers=auth, json={**BODY, "name": "RODAR   testes!"}).status_code == 409
    assert (
        client.post(
            "/v1/commands", headers=auth, json={**BODY, "name": "outro", "aliases": ["Testar Tudo"]}
        ).status_code
        == 409
    )


def test_mesmo_nome_em_outra_conta_pode(client):
    a = signup(client, "a@exemplo.com")
    b = signup(client, "b@exemplo.com")
    assert client.post("/v1/commands", headers=a, json=BODY).status_code == 201
    assert client.post("/v1/commands", headers=b, json=BODY).status_code == 201


def test_conta_b_nao_ve_edita_nem_apaga_o_atalho_de_a(client):
    a = signup(client, "a@exemplo.com")
    b = signup(client, "b@exemplo.com")
    item = client.post("/v1/commands", headers=a, json=BODY).json()
    assert client.get("/v1/commands", headers=b).json() == []
    assert client.put(f"/v1/commands/{item['id']}", headers=b, json=BODY).status_code == 404
    assert client.delete(f"/v1/commands/{item['id']}", headers=b).status_code == 404
    assert len(client.get("/v1/commands", headers=a).json()) == 1


def test_limite_de_30_atalhos_por_conta(client):
    auth = signup(client, "a@exemplo.com")
    for i in range(30):
        assert (
            client.post(
                "/v1/commands", headers=auth, json={**BODY, "name": f"comando {i:02d}", "aliases": []}
            ).status_code
            == 201
        )
    r = client.post("/v1/commands", headers=auth, json={**BODY, "name": "um a mais", "aliases": []})
    assert r.status_code == 409 and r.json()["detail"] == "quota_commands"


def test_exige_autenticacao_e_acoes_entram_no_rastro_so_com_o_nome(client):
    assert client.get("/v1/commands").status_code == 401
    auth = signup(client, "a@exemplo.com")
    item = client.post("/v1/commands", headers=auth, json=BODY).json()
    client.delete(f"/v1/commands/{item['id']}", headers=auth)
    rows = client.get("/v1/audit", headers=auth).json()
    assert [(r["kind"], r["label"]) for r in rows] == [
        ("painel:apagar_atalho", "Rodar testes"),
        ("painel:criar_atalho", "Rodar testes"),
    ]
    assert "suite de testes" not in str(rows)  # o texto da instrucao nao entra no rastro


def test_excluir_a_conta_apaga_os_atalhos(client):
    auth = signup(client, "a@exemplo.com")
    client.post("/v1/commands", headers=auth, json=BODY)
    client.request("DELETE", "/v1/account", headers=auth, json={"password": "senha-bem-longa"})
    assert client.app.state.repo.count_shortcuts() == 0
