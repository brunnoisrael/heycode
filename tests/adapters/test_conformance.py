import sys
import time

import conformance
import pytest

from heycode.adapters import AiderAdapter, Capability, ClaudeAdapter, CodexAdapter
from heycode.store.db import Store
from heycode.supervisor.manager import Supervisor


class BrokenSupervisor:
    def start(self, *a, **k):
        raise RuntimeError("falha no supervisor")

    cancel = status = start


class BrokenStore:
    def add_instruction(self, *a, **k):
        raise RuntimeError("falha no banco")


@pytest.fixture(params=[ClaudeAdapter, CodexAdapter, AiderAdapter], ids=["claude", "codex", "aider"])
def adapter(request):
    return request.param(BrokenSupervisor(), BrokenStore())


def test_declara_capacidades(adapter):
    conformance.check_declara_capacidades(adapter)


def test_chamar_nao_declarada_levanta_unsupported(adapter):
    conformance.check_chamar_nao_declarada_levanta_unsupported(adapter)


def test_erro_do_adaptador_nao_derruba_o_agente(adapter):
    conformance.check_erro_do_adaptador_nao_derruba_o_agente(adapter)


def test_so_o_claude_instrui_sessao_aberta():
    caps = {
        a.name: a.capabilities()
        for a in (ClaudeAdapter(None, None), CodexAdapter(None, None), AiderAdapter(None, None))
    }
    assert Capability.INSTRUCT_OPEN_SESSION in caps["claude"]
    assert Capability.INSTRUCT_OPEN_SESSION not in caps["codex"] | caps["aider"]
    assert all(Capability.RESUME not in c for c in caps.values())


def test_adaptador_real_inicia_le_resultado_e_instrui():
    store = Store()
    sup = Supervisor(store, {"claude": [sys.executable, "-c", "print('feito')"]})
    claude = ClaudeAdapter(sup, store)
    run = claude.start(".", "x")
    end = time.time() + 15
    while claude.result(run)["status"] == "rodando" and time.time() < end:
        time.sleep(0.05)
    assert claude.result(run)["status"] == "concluida"
    assert isinstance(claude.instruct("proj", "avise"), int)
