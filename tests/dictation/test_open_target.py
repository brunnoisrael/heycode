"""Ditado com destino "aberto": confirma e enfileira para a sessao aberta, sem iniciar run (ADR 0018)."""
import pytest

from heycode.dictation.service import Dictation

SK = "sk-abcdef1234567890XYZ"


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class Env:
    def __init__(self):
        self.clock = Clock()
        self.runs, self.queued = [], []
        self.session = {"agent": "claude", "project": "painel", "status": "trabalhando"}
        self.d = Dictation(self._start, clock=self.clock, open_session=lambda: self.session, enqueue=self._enqueue)

    def _start(self, agent, text, project):
        self.runs.append((agent, text, project))
        return 42

    def _enqueue(self, agent, text, project):
        self.queued.append((agent, text, project))
        return 7


@pytest.fixture
def env():
    return Env()


def test_aberto_rele_com_o_projeto_da_sessao_e_nao_envia_nada(env):
    r = env.d.propose("", "rode os testes", target="aberto")
    assert r == {"speech": "Entendi, para o agente aberto no projeto painel: rode os testes. Confirma?", "ok": True}
    assert env.queued == [] and env.runs == []


def test_aberto_confirmado_enfileira_para_a_sessao_e_nao_inicia_run(env):
    env.d.propose("", "rode os testes", target="aberto")
    r = env.d.confirm()
    assert env.queued == [("claude", "rode os testes", "painel")]
    assert env.runs == []
    assert r == {"speech": "Instrução na fila do agente aberto no projeto painel. "
                           "Ele recebe ao terminar o turno atual.", "instruction_id": 7}
    assert "run_id" not in r


def test_aberto_ignora_agente_e_projeto_do_pedido(env):
    env.session = {"agent": "codex", "project": "api", "status": "aguardando"}
    env.d.propose("aider", "x", "outro", target="aberto")
    env.d.confirm()
    assert env.queued == [("codex", "x", "api")]


def test_aberto_com_sessao_parada_avisa_que_so_chega_no_proximo_turno(env):
    env.session["status"] = "concluido"
    env.d.propose("", "x", target="aberto")
    assert env.d.confirm()["speech"] == ("Instrução na fila do agente aberto no projeto painel. "
                                        "Ele está parado e só recebe ao fim do próximo turno.")
    assert len(env.queued) == 1


def test_aberto_sem_sessao_recusa_e_nao_deixa_pendencia(env):
    env.session = None
    r = env.d.propose("", "x", target="aberto")
    assert r == {"speech": "Não achei nenhum agente aberto com atividade recente. Nada foi enviado.", "ok": False}
    assert env.d.confirm()["speech"] == "Não há nada para confirmar."
    assert env.queued == []


def test_aberto_sem_fila_ligada_recusa():
    d = Dictation(lambda *a: 1, open_session=lambda: {"agent": "claude", "project": "p", "status": "trabalhando"})
    assert d.propose("", "x", target="aberto")["ok"] is False


def test_aberto_falha_ao_consultar_sessao_recusa(env):
    def boom():
        raise RuntimeError("db")
    d = Dictation(lambda *a: 1, open_session=boom, enqueue=lambda *a: 1)
    assert d.propose("", "x", target="aberto")["ok"] is False


def test_aberto_valida_texto_como_o_ditado(env):
    assert env.d.propose("", "   ", target="aberto")["ok"] is False
    assert env.d.propose("", "a" * 301, target="aberto")["ok"] is False
    assert env.d.propose("", "a" * 300, target="aberto")["ok"] is True


def test_aberto_mascara_segredo_na_fala_e_entrega_o_original(env):
    r = env.d.propose("", f"use {SK} aqui", target="aberto")
    assert SK not in r["speech"] and "[segredo]" in r["speech"]
    env.d.confirm()
    assert env.queued[0][1] == f"use {SK} aqui"


def test_aberto_confirmar_duas_vezes_enfileira_uma_so(env):
    env.d.propose("", "x", target="aberto")
    env.d.confirm()
    assert env.d.confirm()["speech"] == "Não há nada para confirmar."
    assert len(env.queued) == 1


def test_aberto_expira_em_60s(env):
    env.d.propose("", "x", target="aberto")
    env.clock.t += 61
    assert env.d.confirm()["speech"] == "O ditado expirou. Nada foi enviado."
    assert env.queued == []


def test_aberto_cancelado_nao_enfileira(env):
    env.d.propose("", "x", target="aberto")
    assert env.d.cancel()["speech"] == "Ditado cancelado."
    assert env.d.confirm()["speech"] == "Não há nada para confirmar."
    assert env.queued == []


def test_novo_ditado_substitui_o_pendente_entre_destinos(env):
    env.d.propose("", "para o aberto", target="aberto")
    env.d.propose("codex", "para uma run")
    r = env.d.confirm()
    assert r == {"speech": "Enviado ao codex.", "run_id": 42}
    assert env.runs == [("codex", "para uma run", None)] and env.queued == []


def test_falha_ao_enfileirar_vira_fala_mascarada(env):
    def boom(agent, text, project):
        raise RuntimeError(f"falhou com {SK}")
    d = Dictation(lambda *a: 1, open_session=lambda: env.session, enqueue=boom)
    d.propose("", "x", target="aberto")
    s = d.confirm()["speech"]
    assert s.startswith("Não consegui pôr a instrução na fila") and SK not in s


def test_destino_desconhecido_recusa(env):
    assert env.d.propose("claude", "x", target="outro")["ok"] is False
    assert env.d.confirm()["speech"] == "Não há nada para confirmar."


def test_peca_ao_agente_continua_igual(env):
    assert env.d.propose("claude", "faz x")["speech"] == "Entendi, para o claude: faz x. Confirma?"
    assert env.d.confirm() == {"speech": "Enviado ao claude.", "run_id": 42}
    assert env.runs == [("claude", "faz x", None)] and env.queued == []
    assert env.d.propose("", "faz x")["ok"] is False  # sem agente, "run" continua recusando
