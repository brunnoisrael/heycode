import subprocess

from lint import run_lint


class Runner:
    def __init__(self, code=0, missing=False):
        self.calls = []
        self.code = code
        self.missing = missing

    def __call__(self, cmd, **kwargs):
        self.calls.append(cmd)
        if self.missing:
            raise FileNotFoundError(cmd[0])
        return subprocess.CompletedProcess(cmd, self.code, stdout="x.py:1: E999\n", stderr="")


def test_sem_python_nao_roda_nada():
    r = Runner()
    assert run_lint(["README.md", "a.js"], r) == []
    assert r.calls == []


def test_python_limpo_passa():
    r = Runner(code=0)
    assert run_lint(["bridge/a.py"], r) == []
    assert any("check" in c for c in r.calls[0] + (r.calls[1] if len(r.calls) > 1 else []))


def test_python_com_erro_falha():
    errs = run_lint(["bridge/a.py"], Runner(code=1))
    assert errs and errs[0].startswith("G6")


def test_ferramenta_ausente_falha_fechada():
    errs = run_lint(["bridge/a.py"], Runner(missing=True))
    assert errs and "ruff" in errs[0]


def test_usa_a_configuracao_que_viaja_com_os_gates():
    r = Runner(code=0)
    run_lint(["bridge/a.py"], r)
    for cmd in r.calls:
        i = cmd.index("--config")
        assert cmd[i + 1].replace("\\", "/").endswith("scripts/gates/ruff.toml")


def test_formato_so_nos_arquivos_novos():
    r = Runner(code=0)
    run_lint(["bridge/legado.py", "bridge/novo.py"], r, format_files=["bridge/novo.py"])
    fmt = [c for c in r.calls if "format" in c][0]
    assert "bridge/novo.py" in fmt and "bridge/legado.py" not in fmt
    chk = [c for c in r.calls if "check" in c and "format" not in c][0]
    assert "bridge/legado.py" in chk and "bridge/novo.py" in chk


def test_sem_arquivo_novo_nao_roda_o_formato():
    r = Runner(code=0)
    run_lint(["bridge/legado.py"], r, format_files=[])
    assert not any("format" in c for c in r.calls)
