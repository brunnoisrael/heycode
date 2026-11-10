import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "bridge"))

from store.db import Store


def test_fifo_e_entrega_unica():
    s = Store()
    a = s.add_instruction("primeira")
    s.add_instruction("segunda")
    first = s.pop_instruction("claude", None)
    assert first["id"] == a and first["text"] == "primeira"
    assert set(first) >= {"id", "text", "agent", "project"}
    assert s.pop_instruction("claude", None)["text"] == "segunda"
    assert s.pop_instruction("claude", None) is None


def test_fila_vazia():
    assert Store().pop_instruction("claude", "x") is None


def test_isolamento_por_projeto():
    s = Store()
    s.add_instruction("so do a", project="a")
    assert s.pop_instruction("claude", "b") is None
    assert s.pop_instruction("claude", "a")["text"] == "so do a"


def test_sem_projeto_vale_para_qualquer():
    s = Store()
    s.add_instruction("geral")
    assert s.pop_instruction("claude", "qualquer")["text"] == "geral"


def test_isolamento_por_agente():
    s = Store()
    s.add_instruction("p/ codex", agent="codex")
    assert s.pop_instruction("claude", None) is None
    assert s.pop_instruction("codex", None)["text"] == "p/ codex"


def test_mais_antiga_primeiro_entre_projeto_e_geral():
    s = Store()
    s.add_instruction("geral")
    s.add_instruction("do a", project="a")
    assert s.pop_instruction("claude", "a")["text"] == "geral"
    assert s.pop_instruction("claude", "a")["text"] == "do a"
