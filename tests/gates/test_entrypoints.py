"""Pontos de entrada (main/CLI) dos gates, exercitados em repositorios git temporarios."""

import json
import runpy
import subprocess
import sys
from pathlib import Path

import pytest
from ci_range import main as ci_main
from diff_coverage import main as cov_main
from pre_commit import main as pre_main
from secret_scan import scan_staged

GATES = Path(__file__).resolve().parents[2] / "scripts" / "gates"
SPEC = "docs/superpowers/specs/s.md"
FENCE = chr(96) * 3


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=a@b.c", "-c", "user.name=t", *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path, monkeypatch):
    git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / "docs/superpowers/specs").mkdir(parents=True)
    (tmp_path / SPEC).write_text("# S\n\nStatus: aprovada\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("r\n", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "chore: base")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def commit(repo, msg, files):
    for rel, text in files.items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "--no-verify", "-m", msg)


# ---- ci_range.main -------------------------------------------------------------


def test_ci_range_ok(repo, capsys):
    git(repo, "checkout", "-q", "-b", "pr")
    commit(repo, "docs: a", {"docs/a.md": "a\n"})
    assert ci_main(["ci", "range", "main", "HEAD"], repo) == 0


def test_ci_range_com_erro_imprime_e_retorna_1(repo, capsys):
    git(repo, "checkout", "-q", "-b", "pr")
    commit(repo, "feat: sem trailer", {"src/heycode/a.py": "x = 1\n"})
    assert ci_main(["ci", "range", "main", "HEAD"], repo) == 1
    assert "ci:" in capsys.readouterr().err


def test_ci_modo_approvals_nao_existe_mais(repo):
    assert ci_main(["ci", "approvals", "main", "HEAD"], repo) == 1


def test_ci_modo_desconhecido_falha(repo):
    assert ci_main(["ci", "xyz"], repo) == 1


# ---- diff_coverage.main --------------------------------------------------------


def _cov_repo(repo, executed, missing):
    git(repo, "checkout", "-q", "-b", "pr")
    commit(repo, "feat: a", {"src/heycode/a.py": "a = 1\nb = 2\nc = 3\n"})
    report = {
        "files": {
            "src/heycode/a.py": {"executed_lines": executed, "missing_lines": missing, "missing_branches": []},
        }
    }
    path = repo.parent / (repo.name + "-cov.json")
    path.write_text(json.dumps(report), encoding="utf-8")
    return str(path)


def test_diff_coverage_main_passa_com_tudo_coberto(repo):
    assert cov_main(["x", "main", "HEAD", _cov_repo(repo, [1, 2, 3], [])]) == 0


def test_diff_coverage_main_falha_com_cobertura_baixa(repo, capsys):
    assert cov_main(["x", "main", "HEAD", _cov_repo(repo, [1], [2, 3])]) == 1
    assert "G7" in capsys.readouterr().err


# ---- evidence / workflow_pins como scripts ------------------------------------


def _run_script(name, monkeypatch, argv=None):
    monkeypatch.setattr(sys, "argv", [name, *(argv or [])])
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(GATES / name), run_name="__main__")
    return exc.value.code


def test_evidence_script(monkeypatch):
    monkeypatch.setenv("GATES_RESULT", "success")
    monkeypatch.setenv("TESTS_RESULT", "success")
    assert _run_script("evidence.py", monkeypatch) == 0
    monkeypatch.setenv("GATES_RESULT", "failure")
    assert _run_script("evidence.py", monkeypatch) == 1


def test_workflow_pins_script(tmp_path, monkeypatch):
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    (wf / "a.yml").write_text("steps:\n  - uses: actions/checkout@v4\n", encoding="utf-8")
    assert _run_script("workflow_pins.py", monkeypatch) == 1
    (wf / "a.yml").write_text("steps:\n  - run: echo oi\n", encoding="utf-8")
    assert _run_script("workflow_pins.py", monkeypatch) == 0


# ---- secret_scan -----------------------------------------------------------------

FAKE = "BRIDGE_SECRET=" + "k9Xv2LmQ8rTz4WnB7yHc1JdF5gSa3PeU"


def test_scan_staged_e_script(repo, monkeypatch):
    (repo / ".env.exemplo").write_text(FAKE + "\n", encoding="utf-8")
    git(repo, "add", "-A")
    assert scan_staged()
    assert _run_script("secret_scan.py", monkeypatch) == 1


def test_secret_scan_script_com_intervalo(repo, monkeypatch):
    git(repo, "checkout", "-q", "-b", "pr")
    commit(repo, "chore: x", {".env.exemplo": FAKE + "\n"})
    assert _run_script("secret_scan.py", monkeypatch, ["main", "HEAD"]) == 1


# ---- pre_commit.main --------------------------------------------------------------


def test_pre_commit_main_limpo(repo, capsys):
    (repo / "notas.md").write_text("oi\n", encoding="utf-8")
    git(repo, "add", "-A")
    assert pre_main() == 0


def test_pre_commit_main_arquitetura_sem_adr_falha(repo, capsys):
    (repo / "src" / "heycode" / "policy").mkdir(parents=True)
    (repo / "src/heycode/policy/engine.py").write_text("x = 1\n", encoding="utf-8")
    git(repo, "add", "-A")
    assert pre_main() == 1
    assert "ADR" in capsys.readouterr().err


def test_pre_commit_main_avisa_teste_ausente_sem_bloquear(repo, capsys):
    (repo / "src" / "heycode").mkdir(parents=True)
    (repo / "src/heycode/a.py").write_text("x = 1\n", encoding="utf-8")
    git(repo, "add", "-A")
    assert pre_main() == 0
    assert "G4" in capsys.readouterr().err


def test_pre_commit_main_renomear_arquivo_legado_nao_exige_formato(repo, capsys):
    (repo / "legacy").mkdir()
    (repo / "legacy/a.py").write_text("x   =   1\n" * 5, encoding="utf-8")  # fora do padrao do ruff
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "--no-verify", "-m", "chore: legado")
    git(repo, "mv", "legacy/a.py", "legacy/b.py")
    assert pre_main() == 0


def test_pre_commit_main_arquivo_novo_fora_do_formato_falha(repo, capsys):
    (repo / "legacy").mkdir()
    (repo / "legacy/c.py").write_text("x   =   1\n" * 5, encoding="utf-8")
    git(repo, "add", "-A")
    assert pre_main() == 1
    assert "G6" in capsys.readouterr().err


def test_lint_main_so_acusa_linhas_alteradas(repo, capsys):
    from lint import main as lint_main

    (repo / "legacy").mkdir()
    (repo / "legacy/a.py").write_text("import os\nimport sys\nx = 1\n", encoding="utf-8")  # F401 legado
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "--no-verify", "-m", "chore: legado")
    git(repo, "checkout", "-q", "-b", "pr")
    commit(repo, "fix: toca so a ultima linha", {"legacy/a.py": "import os\nimport sys\nx = 2\n"})
    assert lint_main(["lint", "main", "HEAD"]) == 0
    commit(repo, "fix: nova linha com erro", {"legacy/a.py": "import os\nimport sys\nx = 2\nimport json\n"})
    assert lint_main(["lint", "main", "HEAD"]) == 1
    assert "F401" in capsys.readouterr().err
