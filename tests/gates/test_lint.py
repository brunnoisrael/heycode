import subprocess
from pathlib import Path

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
    assert run_lint(["src/heycode/a.py"], r) == []
    assert any("check" in c for c in r.calls[0] + (r.calls[1] if len(r.calls) > 1 else []))


def test_python_com_erro_falha():
    errs = run_lint(["src/heycode/a.py"], Runner(code=1))
    assert errs and errs[0].startswith("G6")


def test_ferramenta_ausente_falha_fechada():
    errs = run_lint(["src/heycode/a.py"], Runner(missing=True))
    assert errs and "ruff" in errs[0]


def test_usa_a_configuracao_que_viaja_com_os_gates():
    r = Runner(code=0)
    run_lint(["src/heycode/a.py"], r)
    for cmd in r.calls:
        i = cmd.index("--config")
        assert cmd[i + 1].replace("\\", "/").endswith("scripts/gates/ruff.toml")


def test_formato_so_nos_arquivos_novos():
    r = Runner(code=0)
    run_lint(["src/heycode/legado.py", "src/heycode/novo.py"], r, format_files=["src/heycode/novo.py"])
    fmt = [c for c in r.calls if "format" in c][0]
    assert "src/heycode/novo.py" in fmt and "src/heycode/legado.py" not in fmt
    chk = [c for c in r.calls if "check" in c and "format" not in c][0]
    assert "src/heycode/legado.py" in chk and "src/heycode/novo.py" in chk


def test_sem_arquivo_novo_nao_roda_o_formato():
    r = Runner(code=0)
    run_lint(["src/heycode/legado.py"], r, format_files=[])
    assert not any("format" in c for c in r.calls)


def _json_runner(diags, code=1):
    import json

    class R:
        calls = []

        def __call__(self, cmd, **kwargs):
            self.calls.append(cmd)
            return subprocess.CompletedProcess(cmd, code, stdout=json.dumps(diags), stderr="")

    return R()


def _diag(path, row, code="E501"):
    return {"code": code, "message": "x", "filename": str(Path(path).resolve()), "location": {"row": row, "column": 1}}


def test_check_so_reporta_linhas_alteradas():
    r = _json_runner([_diag("bridge/a.py", 5), _diag("bridge/a.py", 50)])
    errs = run_lint(["bridge/a.py"], r, format_files=[], added_lines={"bridge/a.py": {5, 6}})
    assert len(errs) == 1 and "bridge/a.py:5" in errs[0] and errs[0].startswith("G6")


def test_check_sem_linhas_alteradas_no_arquivo_passa():
    r = _json_runner([_diag("bridge/legado.py", 7)])
    assert run_lint(["bridge/legado.py"], r, format_files=[], added_lines={"bridge/legado.py": set()}) == []


def test_check_com_added_lines_pede_saida_json():
    r = _json_runner([])
    run_lint(["bridge/a.py"], r, format_files=[], added_lines={"bridge/a.py": {1}})
    assert "--output-format" in r.calls[0] and "json" in r.calls[0]


def test_saida_ilegivel_do_ruff_falha_fechado():
    class Bad:
        def __call__(self, cmd, **kwargs):
            return subprocess.CompletedProcess(cmd, 2, stdout="nao e json", stderr="boom")

    errs = run_lint(["bridge/a.py"], Bad(), format_files=[], added_lines={"bridge/a.py": {1}})
    assert errs and errs[0].startswith("G6")
