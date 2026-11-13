import time

import pytest

from heycode.store.db import Store


def test_politica_padrao():
    assert Store().get_policy(None, None) == {"mode": "manual", "report_on_end": False}


def test_precedencia_quatro_niveis():
    s = Store()
    s.set_policy(mode="auto")
    s.set_policy(mode="decisoes", agent="claude")
    s.set_policy(mode="manual", project="x")
    s.set_policy(mode="auto", agent="claude", project="x")
    assert s.get_policy(None, None)["mode"] == "auto"
    assert s.get_policy("claude", None)["mode"] == "decisoes"
    assert s.get_policy(None, "x")["mode"] == "manual"
    assert s.get_policy("claude", "x")["mode"] == "auto"
    # agente sem regra propria cai no projeto
    assert s.get_policy("outro", "x")["mode"] == "manual"


def test_precedencia_por_campo():
    s = Store()
    s.set_policy(report_on_end=True)
    s.set_policy(mode="auto", project="x")
    assert s.get_policy("claude", "x") == {"mode": "auto", "report_on_end": True}


def test_modo_invalido():
    s = Store()
    with pytest.raises(ValueError):
        s.set_policy(mode="x")
    assert s.get_policy(None, None)["mode"] == "manual"


def test_fluxo_aprovacao():
    s = Store()
    a = s.add_approval("claude", "p", "Bash", "ls", "s1")
    b = s.add_approval("claude", "p", "Bash", "pwd", "s1")
    assert [x["id"] for x in s.pending_approvals()] == [a, b]
    s.resolve_approval(a, "allow")
    assert [x["id"] for x in s.pending_approvals()] == [b]
    got = s.get_approval(a)
    assert got["decision"] == "allow" and got["command"] == "ls"
    assert isinstance(got["t"], float)
    assert s.get_approval(999) is None


def test_expire_pending():
    s = Store()
    a = s.add_approval("c", "p", "Bash", "ls", "s")
    b = s.add_approval("c", "p", "Bash", "pwd", "s")
    s.resolve_approval(a, "deny")
    assert s.expire_pending() == 1
    assert s.get_approval(b)["decision"] == "expired"
    assert s.get_approval(a)["decision"] == "deny"
    assert s.pending_approvals() == []


def test_newest_session():
    s = Store()
    assert s.newest_session() is None
    s.upsert_session("a", "claude", "p", "running")
    time.sleep(0.01)
    s.upsert_session("b", "claude", "q", "idle", detail="d", summary="r")
    n = s.newest_session()
    assert n["session_id"] == "b" and n["summary"] == "r" and n["detail"] == "d"
    time.sleep(0.01)
    s.upsert_session("a", "claude", "p", "done")
    n = s.newest_session()
    assert n["session_id"] == "a" and n["status"] == "done"
    assert isinstance(n["updated"], float)


def test_log():
    s = Store()
    s.log("evento", {"k": 1})


def test_persistencia(tmp_path):
    p = str(tmp_path / "b.db")
    s = Store(p)
    s.set_policy(mode="auto", agent="claude")
    s.close() if hasattr(s, "close") else None
    assert Store(p).get_policy("claude", None)["mode"] == "auto"


def test_reported_resumo_e_trava_no_store(tmp_path):
    path = str(tmp_path / "x.db")
    s = Store(path)
    rid = s.create_run("claude", "p", "x", "/x")
    s.update_run(rid, status="concluida")
    assert s.first_unreported() is None
    s.mark_unreported(rid)
    s.upsert_session("s1", "claude", "p", "concluido", "", "resumo")
    s.upsert_session("s1", "claude", "p", "trabalhando", "x")  # sem summary: preserva
    s.set_pin_lock(2, 99.0)
    s.close()
    s = Store(path)
    assert s.first_unreported()["id"] == rid
    assert s.newest_session()["summary"] == "resumo"
    assert s.get_pin_lock() == {"fails": 2, "until": 99.0}
    s.mark_reported(rid)
    assert s.first_unreported() is None
    s.close()
