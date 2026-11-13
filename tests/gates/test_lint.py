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
