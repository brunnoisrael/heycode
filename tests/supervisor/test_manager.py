import sys
import threading
import time

import pytest

from bridge.store.db import Store
from bridge.supervisor.manager import Supervisor


def fake(code):
    return {a: [sys.executable, "-c", code] for a in ("claude", "codex", "aider")}


def wait_done(sup, rid, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        r = sup.status(rid)
        if r["status"] != "rodando":
            return r
        time.sleep(0.05)
    raise AssertionError("nao terminou")


def test_sucesso_grava_resumo_e_chama_on_finish():
    got = []
    done = threading.Event()
    sup = Supervisor(Store(), fake("print('linha1'); print('tudo certo')"),
                     on_finish=lambda r: (got.append(r), done.set()))
    rid = sup.start("claude", "faz", ".", "auto")
    r = wait_done(sup, rid)
    assert done.wait(5)
    assert r["status"] == "concluida" and r["exit_code"] == 0
    assert "tudo certo" in r["summary"] and r["t_end"]
    assert got[0]["id"] == rid and got[0]["status"] == "concluida"


def test_segredo_mascarado_no_resumo():
    sup = Supervisor(Store(), fake("print('chave sk-abcdefghijklmnopqrstuvwx fim')"))
    r = wait_done(sup, sup.start("codex", "x", ".", "manual"))
    assert "[segredo]" in r["summary"] and "sk-abcdefgh" not in r["summary"]


def test_resumo_limitado_a_400():
    sup = Supervisor(Store(), fake("print('a'*2000)"))
    r = wait_done(sup, sup.start("aider", "x", ".", "manual"))
    assert 0 < len(r["summary"]) <= 400


def test_claude_json_usa_campo_result():
    code = "import json; print(json.dumps({'type':'result','result':'resposta final'}))"
    sup = Supervisor(Store(), fake(code))
    r = wait_done(sup, sup.start("claude", "x", ".", "manual"))
    assert r["summary"] == "resposta final"


def test_codex_le_ultima_mensagem_do_arquivo():
    # o fake recebe o caminho de -o em sys.argv e escreve a ultima mensagem la
    code = ("import sys\n"
            "open(sys.argv[sys.argv.index('-o') + 1], 'w', encoding='utf-8').write('msg final')\n"
            "print('{\"evento\": 1}')")
    sup = Supervisor(Store(), fake(code))
    r = wait_done(sup, sup.start("codex", "x", ".", "manual"))
    assert r["summary"] == "msg final"


def test_codigo_3_vira_falhou_com_cauda_mascarada():
    code = ("import sys\n"
            "for i in range(20): print('l%d' % i)\n"
            "print('erro password=hunter2', file=sys.stderr)\n"
            "sys.exit(3)")
    sup = Supervisor(Store(), fake(code))
    r = wait_done(sup, sup.start("codex", "x", ".", "auto"))
    assert r["status"] == "falhou" and r["exit_code"] == 3
    assert "l19" in r["summary"] and "l0\n" not in r["summary"]
    assert "hunter2" not in r["summary"]


def test_executavel_inexistente_vira_falhou():
    sup = Supervisor(Store(), {"claude": ["nao-existe-xyz"]})
    r = wait_done(sup, sup.start("claude", "x", ".", "auto"))
    assert r["status"] == "falhou"


def test_agente_desconhecido():
    with pytest.raises(ValueError):
        Supervisor(Store(), fake("pass")).start("gemini", "x", ".", "auto")


def test_cancel_mata_arvore_e_marca_cancelada():
    code = ("import subprocess, sys, time\n"
            "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
            "print('filho', flush=True)\n"
            "time.sleep(60)")
    store = Store()
    sup = Supervisor(store, fake(code))
    rid = sup.start("claude", "x", ".", "auto")
    end = time.time() + 10
    while time.time() < end and not store.get_run(rid)["pid"]:
        time.sleep(0.05)
    time.sleep(0.5)
    t0 = time.time()
    assert sup.cancel(rid) is True
    r = wait_done(sup, rid, 10)
    assert r["status"] == "cancelada" and time.time() - t0 < 8
    assert sup.cancel(rid) is False
    assert sup.cancel(9999) is False


def test_status_inexistente():
    assert Supervisor(Store(), fake("pass")).status(5) is None
