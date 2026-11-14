import json
import sys
import threading
import time

import httpx
import pytest

from heycode.commands import CommandRunner

PY = sys.executable


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def world(tmp_path, clock):
    """Registro em arquivo + executor com eventos e transporte HTTP falso."""
    path = tmp_path / "commands.json"
    events, requests = [], []
    secrets = {"HA_TOKEN": "Bearer token-do-ha-123"}
    replies = {"status": 200, "text": "feito", "redirect": False, "boom": False}

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if replies["boom"]:
            raise httpx.ConnectError("sem rota")
        if replies["redirect"]:
            return httpx.Response(302, headers={"Location": "https://outro.example.com/"})
        return httpx.Response(replies["status"], text=replies["text"])

    def put(*cmds):
        path.write_text(json.dumps({"version": 1, "commands": list(cmds)}), encoding="utf-8")

    runner = CommandRunner(
        path, secrets=lambda: secrets, clock=clock, on_event=events.append, transport=httpx.MockTransport(handler)
    )
    return runner, put, events, requests, replies, tmp_path


def script(code, name="rodar tarefa", risk="leitura", **over):
    d = {"name": name, "type": "script", "risk": risk, "argv": [PY, "-c", code]}
    d.update(over)
    return d


def hook(name="acender luz", risk="confirmar", **over):
    d = {"name": name, "type": "webhook", "risk": risk, "url": "https://casa.exemplo.com/luz", "method": "POST"}
    d.update(over)
    return d


# ---------- scripts ----------


def test_leitura_roda_na_hora_e_fala_o_resultado(world):
    runner, put, events, *_ = world
    put(script("print('oi do script')"))
    r = runner.start("rodar tarefa")
    assert r["ok"] and r["label"] == "rodar tarefa" and "pending" not in r
    assert "terminou com sucesso" in r["speech"] and "oi do script" in r["speech"]
    (ev,) = events
    assert (ev["name"], ev["risk"], ev["type"], ev["outcome"], ev["exit_code"]) == (
        "rodar tarefa",
        "leitura",
        "script",
        "ok",
        0,
    )
    assert "oi do script" not in json.dumps(events)  # a saida nunca vai para o historico


def test_falha_do_script_fala_o_codigo_de_saida(world):
    runner, put, events, *_ = world
    put(script("import sys; print('quebrou'); sys.exit(3)"))
    r = runner.start("rodar tarefa")
    assert not r["ok"] and "falhou com código 3" in r["speech"] and events[0]["outcome"] == "falhou"


def test_saida_com_segredo_sai_mascarada_e_limitada(world):
    runner, put, *_ = world
    put(script("print('token ghp_' + 'a'*36); print('x'*100000)"))
    speech = runner.start("rodar tarefa")["speech"]
    assert "ghp_" not in speech and len(speech) < 500


def test_timeout_mata_o_processo_e_avisa(world):
    runner, put, events, *_ = world
    put(script("import time; time.sleep(60)", timeout=1))
    t0 = time.time()
    r = runner.start("rodar tarefa")
    assert time.time() - t0 < 15
    assert not r["ok"] and "tempo limite de 1 segundo" in r["speech"] and events[0]["outcome"] == "timeout"


def test_programa_inexistente(world):
    runner, put, *_ = world
    put({"name": "rodar tarefa", "type": "script", "risk": "leitura", "argv": ["programa-que-nao-existe-xyz"]})
    r = runner.start("rodar tarefa")
    assert not r["ok"] and "Não encontrei o programa" in r["speech"]


def test_sem_shell_o_argumento_e_literal(world):
    runner, put, *_ = world
    put(
        script("import sys; print(sys.argv[1])")
        | {"argv": [PY, "-c", "import sys; print(sys.argv[1])", "a; echo PWNED && b"]}
    )
    assert "a; echo PWNED && b" in runner.start("rodar tarefa")["speech"]


def test_a_fala_nunca_chega_ao_comando(world):
    runner, put, *_ = world
    put(script("import sys; print('argc', len(sys.argv))"))
    assert "argc 1" in runner.start("  Rodar   a TAREFA?  ")["speech"]


def test_ambiente_minimo_e_env_pass_explicito(world, monkeypatch):
    runner, put, *_ = world
    monkeypatch.setenv("MINHA_CHAVE_X", "valor-secreto")
    code = "import os; print('v=' + str(os.environ.get('MINHA_CHAVE_X')))"
    put(script(code))
    assert "v=None" in runner.start("rodar tarefa")["speech"]
    put(script(code, env_pass=["MINHA_CHAVE_X"]))
    runner._last_run.clear()
    assert "v=valor-secreto" in runner.start("rodar tarefa")["speech"]


def test_cwd_definido_no_registro(world):
    runner, put, _, _, _, tmp = world
    sub = tmp / "pasta"
    sub.mkdir()
    put(script("import os; print(os.getcwd())", cwd=str(sub)))
    assert sub.name in runner.start("rodar tarefa")["speech"]


# ---------- niveis de risco ----------


def test_confirmar_pergunta_antes_e_so_roda_depois(world):
    runner, put, events, _, _, tmp = world
    marker = tmp / "rodou.txt"
    put(script(f"open({str(marker)!r}, 'w').write('x')", risk="confirmar", description="grava um arquivo"))
    r = runner.start("rodar tarefa")
    assert r["pending"] == {"risk": "confirmar"} and "Confirma?" in r["speech"] and "grava um arquivo" in r["speech"]
    assert not marker.exists() and events == []
    done = runner.confirm()
    assert done["ok"] and done["done"] is True and marker.exists() and events[0]["outcome"] == "ok"
    assert runner.confirm()["done"] is False  # a confirmacao vale uma vez


def test_pin_exige_o_pin_verificado_pela_ponte(world):
    runner, put, _, _, _, tmp = world
    marker = tmp / "pin.txt"
    put(script(f"open({str(marker)!r}, 'w').write('x')", risk="pin"))
    r = runner.start("rodar tarefa")
    assert r["pending"] == {"risk": "pin"} and "PIN" in r["speech"]
    for pin_ok in (None, False):
        refused = runner.confirm(pin_ok=pin_ok)
        assert refused["done"] is False and not marker.exists()
    ok = runner.confirm(pin_ok=True)
    assert ok["done"] is True and marker.exists()


def test_pendencia_expira_em_120s(world, clock):
    runner, put, *_ = world
    put(script("print(1)", risk="confirmar"))
    runner.start("rodar tarefa")
    clock.t += 121
    r = runner.confirm()
    assert r["done"] is False and "Não há comando aguardando" in r["speech"]


def test_novo_pedido_substitui_a_pendencia_e_cancelar_limpa(world):
    runner, put, events, *_ = world
    put(script("print('a')", "tarefa alfa", "confirmar"), script("print('b')", "tarefa beta", "confirmar"))
    runner.start("tarefa alfa")
    runner.start("tarefa beta")
    runner.confirm()
    assert [e["name"] for e in events] == ["tarefa beta"]
    runner.start("tarefa alfa")
    assert runner.cancel()["ok"] and runner.confirm()["done"] is False


def test_definicao_alterada_entre_pedir_e_confirmar_invalida(world, clock):
    runner, put, events, *_ = world
    put(script("print('original')", risk="confirmar"))
    runner.start("rodar tarefa")
    put(script("print('trocado')", risk="confirmar"))
    r = runner.confirm()
    assert r["done"] is False and "mudou" in r["speech"] and events == []


def test_comando_desligado_entre_pedir_e_confirmar_invalida(world):
    runner, put, events, *_ = world
    put(script("print(1)", risk="confirmar"))
    runner.start("rodar tarefa")
    runner.disable("rodar tarefa")
    assert runner.confirm()["done"] is False and events == []


def test_um_comando_por_vez_e_intervalo_minimo_de_3s(world, clock):
    runner, put, *_ = world
    put(script("import time; time.sleep(1.5); print('lento')", "lento"), script("print('rapido')", "rapido"))
    out = {}
    t = threading.Thread(target=lambda: out.update(r=runner.start("lento")))
    t.start()
    time.sleep(0.4)
    assert "Já há um comando em execução" in runner.start("rapido")["speech"]
    t.join(10)
    assert "lento" in out["r"]["speech"]
    assert "acabou de rodar" in runner.start("lento")["speech"]  # intervalo de 3 s por comando
    clock.t += 4
    assert "lento" in runner.start("lento")["speech"]


# ---------- casamento e registro ----------


def test_nao_achei_e_ambiguo(world):
    runner, put, *_ = world
    put(script("print(1)", "rodar testes api"), script("print(2)", "rodar testes app"))
    assert "Não achei" in runner.start("fazer cafe")["speech"]
    assert "Mais de um" in runner.start("rodar testes ap")["speech"]


def test_registro_invalido_vira_fala_clara_sem_executar(world):
    runner, put, *_ = world
    put({"name": "rodar tarefa", "type": "script", "risk": "leitura", "argv": []})
    r = runner.start("rodar tarefa")
    assert not r["ok"] and "erro" in r["speech"] and "heycode command" in r["speech"]


def test_sem_arquivo_de_comandos(world):
    runner, *_ = world
    assert "Nenhum comando" in runner.start("qualquer")["speech"]


def test_disable_so_desliga_e_persiste(world):
    runner, put, *_ = world
    put(script("print(1)"))
    assert runner.disable("rodar tarefa")["ok"]
    assert runner.list()[0]["enabled"] is False
    assert "Não achei" in runner.start("rodar tarefa")["speech"]
    assert runner.disable("nao existe")["ok"] is False


def test_list_devolve_so_resumo(world):
    runner, put, *_ = world
    put(script("print('segredo-no-argv')", description="d"), hook(headers={"Authorization": "env:HA_TOKEN"}))
    texto = json.dumps(runner.list())
    assert "segredo-no-argv" not in texto and "casa.exemplo" not in texto and "HA_TOKEN" not in texto


# ---------- webhooks ----------


def test_webhook_confirmar_envia_corpo_fixo_e_cabecalho_resolvido(world):
    runner, put, events, requests, *_ = world
    put(hook(body={"ligar": True}, headers={"Authorization": "env:HA_TOKEN", "X-Fixo": "1"}))
    r = runner.start("acender luz")
    assert "Confirma?" in r["speech"] and requests == []
    done = runner.confirm()
    assert done["ok"] and "respondeu 200" in done["speech"]
    (req,) = requests
    assert req.method == "POST" and json.loads(req.content) == {"ligar": True}
    assert req.headers["authorization"] == "Bearer token-do-ha-123" and req.headers["x-fixo"] == "1"
    texto = json.dumps([done, r, events])
    assert "token-do-ha-123" not in texto and "Authorization" not in texto  # o valor do cabecalho nunca sai


def test_webhook_get_leitura_roda_direto_sem_corpo(world):
    runner, put, _, requests, *_ = world
    put(hook("ver luz", "leitura", method="GET"))
    r = runner.start("ver luz")
    assert r["ok"] and requests[0].method == "GET" and not requests[0].content


def test_webhook_nao_segue_redirecionamento(world):
    runner, put, _, requests, replies, _ = world
    replies["redirect"] = True
    put(hook("ver luz", "leitura", method="GET"))
    r = runner.start("ver luz")
    assert len(requests) == 1 and "redirecionamento" in r["speech"] and not r["ok"]


def test_webhook_erro_http_e_falha_de_conexao(world):
    runner, put, events, _, replies, _ = world
    put(hook("ver luz", "leitura", method="GET"))
    replies["status"] = 500
    assert "respondeu erro 500" in runner.start("ver luz")["speech"]
    runner._last_run.clear()
    replies["boom"] = True
    r = runner.start("ver luz")
    assert "Não consegui chamar" in r["speech"] and events[-1]["outcome"] == "erro"


def test_webhook_corpo_da_resposta_mascarado_e_curto(world):
    runner, put, _, _, replies, _ = world
    replies["text"] = "token ghp_" + "b" * 36 + " " + "z" * 1000
    put(hook("ver luz", "leitura", method="GET"))
    speech = runner.start("ver luz")["speech"]
    assert "ghp_" not in speech and len(speech) < 400


def test_webhook_com_variavel_de_segredo_removida_depois_nao_roda(world):
    runner, put, _, requests, *_ = world
    put(hook("ver luz", "leitura", method="GET", headers={"Authorization": "env:NAO_EXISTE_MAIS"}))
    r = runner.start("ver luz")  # o registro inteiro e invalido sem a variavel: nada e chamado
    assert not r["ok"] and requests == []
