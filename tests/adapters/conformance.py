"""Conformidade unica que todo adaptador de agente deve passar (ADR 0032)."""

import pytest

from heycode.adapters import AgentAdapter, Capability, UnsupportedCapability, invoke

CALLS = {
    "start": (".", "faca algo"),
    "instruct": ("proj", "avise"),
    "cancel": (1,),
    "resume": ("sessao",),
    "result": (1,),
}
CAP_OF = {
    "start": Capability.START,
    "instruct": Capability.INSTRUCT_OPEN_SESSION,
    "cancel": Capability.CANCEL,
    "resume": Capability.RESUME,
    "result": Capability.READ_RESULT,
}


def check_declara_capacidades(adapter: AgentAdapter) -> None:
    assert isinstance(adapter, AgentAdapter)
    caps = adapter.capabilities()
    assert caps and all(isinstance(c, Capability) for c in caps)
    assert Capability.START in caps


def check_chamar_nao_declarada_levanta_unsupported(adapter: AgentAdapter) -> None:
    missing = [m for m, c in CAP_OF.items() if c not in adapter.capabilities()]
    assert missing, "todo adaptador atual deixa ao menos uma capacidade de fora; se nao, atualize o teste"
    for method in missing:
        with pytest.raises(UnsupportedCapability) as e:
            invoke(adapter, method, *CALLS[method])
        assert e.value.capability is CAP_OF[method]


def check_erro_do_adaptador_nao_derruba_o_agente(adapter: AgentAdapter) -> None:
    declared = [m for m, c in CAP_OF.items() if c in adapter.capabilities()]
    assert declared
    for method in declared:
        result = invoke(adapter, method, *CALLS[method])  # nunca levanta, mesmo com backend quebrado
        assert result.ok is False and result.error
