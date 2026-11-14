import sys
import threading
import time

import pytest

from heycode.store.db import Store
from heycode.supervisor.manager import Supervisor


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


# ---------- ADR 0017: resumo de falha legivel ----------

def _falha(payload_expr, extra=""):
    """Fake que imprime o JSON e sai com codigo 1, como o claude e o codex em erro de API."""
    return fake(f"import json, sys\n{extra}\nprint(json.dumps({payload_expr}))\nsys.exit(1)")


def test_falha_do_claude_grava_a_mensagem_e_nao_o_rabo_do_json():
    code = ("{'type':'result','subtype':'success','is_error':True,'result':'API Error: 400 versao antiga',"
            "'usage':{'input_tokens':0},'terminal_reason':'api_error','uuid':'f942b57e'}")
    r = wait_done(sup := Supervisor(Store(), _falha(code)), sup.start("claude", "x", ".", "manual"))
    assert r["status"] == "falhou" and r["exit_code"] == 1
    assert r["summary"] == "API Error: 400 versao antiga"


def test_falha_do_codex_grava_a_mensagem_do_evento():
    code = ("{'type':'turn.failed','error':{'message':json.dumps({'type':'error','status':400,'error':"
            "{'message':'modelo nao suportado','code':'model_not_found'}})}}")
    r = wait_done(sup := Supervisor(Store(), _falha(code, "print('Reading additional input from stdin...')")),
                  sup.start("codex", "x", ".", "manual"))
    assert r["status"] == "falhou" and r["summary"] == "modelo nao suportado"


def test_falha_do_aider_continua_com_a_cauda_da_saida():
    code = "import sys\nprint('{\"result\": \"nao e do aider\"}')\nprint('erro de verdade')\nsys.exit(2)"
    r = wait_done(sup := Supervisor(Store(), fake(code)), sup.start("aider", "x", ".", "manual"))
    assert r["status"] == "falhou" and r["summary"].endswith("erro de verdade")


def test_falha_do_claude_sem_json_cai_na_cauda():
    code = "import sys\nprint('Invalid API key - Please run /login')\nsys.exit(1)"
    r = wait_done(sup := Supervisor(Store(), fake(code)), sup.start("claude", "x", ".", "manual"))
    assert r["status"] == "falhou" and "Please run /login" in r["summary"]


def test_motivo_da_falha_e_mascarado_e_cortado_pelo_comeco():
    code = "{'type':'result','is_error':True,'result':'INICIO token=abc123segredo ' + 'z'*900}"
    r = wait_done(sup := Supervisor(Store(), _falha(code)), sup.start("claude", "x", ".", "manual"))
    assert r["summary"].startswith("INICIO [segredo]") and "abc123segredo" not in r["summary"]
    assert len(r["summary"]) == 400


def test_parser_quebrado_nao_impede_a_finalizacao(monkeypatch):
    import heycode.supervisor.manager as manager
    monkeypatch.setattr(manager, "failure_reason", lambda agent, output: None)
    r = wait_done(sup := Supervisor(Store(), _falha("{'result': 'x'}")), sup.start("claude", "x", ".", "manual"))
    assert r["status"] == "falhou" and "result" in r["summary"]
