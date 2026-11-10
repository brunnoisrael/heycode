import pytest

from bridge.store.db import Store


def test_ciclo_de_status():
    s = Store()
    rid = s.create_run("codex", "proj", "faz algo", "C:/x")
    r = s.get_run(rid)
    assert r["status"] == "rodando" and r["agent"] == "codex" and r["project"] == "proj"
    assert r["prompt"] == "faz algo" and r["cwd"] == "C:/x"
    assert r["t_start"] and r["t_end"] is None and r["pid"] is None
    s.update_run(rid, pid=42)
    assert s.get_run(rid)["pid"] == 42 and s.get_run(rid)["status"] == "rodando"
    s.update_run(rid, status="concluida", summary="ok", exit_code=0)
    r = s.get_run(rid)
    assert (r["status"], r["summary"], r["exit_code"]) == ("concluida", "ok", 0)
    assert r["t_end"] is not None


def test_get_run_inexistente():
    assert Store().get_run(99) is None


def test_status_invalido():
    s = Store()
    rid = s.create_run("claude", "p", "x", ".")
    with pytest.raises(ValueError):
        s.update_run(rid, status="zzz")


def test_latest_run_por_agente():
    s = Store()
    assert s.latest_run() is None
    a = s.create_run("claude", "p", "1", ".")
    b = s.create_run("codex", "p", "2", ".")
    assert s.latest_run()["id"] == b
    assert s.latest_run("claude")["id"] == a
    assert s.latest_run("aider") is None


def test_interrupt_running():
    s = Store()
    a = s.create_run("claude", "p", "1", ".")
    b = s.create_run("codex", "p", "2", ".")
    s.update_run(b, status="concluida")
    assert s.interrupt_running() == 1
    assert s.get_run(a)["status"] == "interrompida" and s.get_run(a)["t_end"] is not None
    assert s.get_run(b)["status"] == "concluida"
    assert s.interrupt_running() == 0
