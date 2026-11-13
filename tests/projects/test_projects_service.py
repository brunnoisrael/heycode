import os
import subprocess
import sys
from pathlib import Path

import pytest

from heycode.projects.service import ProjectCreator, scaffold_project, slugify

REPO = str(Path(__file__).resolve().parents[2])
SK = "sk-abcdef1234567890XYZ"


def git(path, *args):
    return subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True)


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


@pytest.mark.parametrize("name,expected", [
    ("Meu App Legal!", "meu-app-legal"),
    ("../x", "x"),
    ("Bot de Estudos", "bot-de-estudos"),
    ("Calendário Ação", "calendario-acao"),
    ("a" * 60, "a" * 40),
    ("..\\..\\Windows\\sys", "windows-sys"),
])
def test_slugify(name, expected):
    assert slugify(name) == expected


@pytest.mark.parametrize("name", ["", "   ", "!!!", "../", "con", "CON", "nul", "com1", "lpt9", "aux"])
def test_slugify_invalido(name):
    with pytest.raises(ValueError):
        slugify(name)


def test_slugify_corta_sem_hifen_final():
    s = slugify("a" * 39 + " bbb")
    assert len(s) <= 40 and not s.endswith("-")


def test_scaffold_cria_projeto_com_gates(tmp_path):
    path = scaffold_project(str(tmp_path), "meu-app", REPO)
    p = Path(path)
    assert p == tmp_path / "meu-app"
    for rel in ("AGENTS.md", "docs/adr", "docs/superpowers/specs", "scripts/gates/commit_msg.py",
                "scripts/gates/pre_commit.py", "scripts/gates/gates.json", ".githooks/commit-msg",
                ".githooks/pre-commit"):
        assert (p / rel).exists(), rel
    assert not list(p.rglob("__pycache__"))
    assert b"\r\n" not in (p / ".githooks" / "commit-msg").read_bytes()
    assert "gates" in (p / "AGENTS.md").read_text(encoding="utf-8").lower()
    assert git(p, "branch", "--show-current").stdout.strip() == "main"
    assert git(p, "config", "core.hooksPath").stdout.strip() == ".githooks"
    assert git(p, "log", "--format=%s").stdout.splitlines() == ["chore: scaffold"]
    assert git(p, "status", "--porcelain").stdout.strip() == ""


def test_hooks_funcionam_no_projeto_novo(tmp_path):
    p = Path(scaffold_project(str(tmp_path), "novo", REPO))
    (p / "a.txt").write_text("x", encoding="utf-8")
    git(p, "add", "a.txt")
    bad = git(p, "commit", "-m", "feat: algo sem spec")
    assert bad.returncode != 0
    assert "Spec" in bad.stderr + bad.stdout
    spec = p / "docs" / "superpowers" / "specs" / "s.md"
    spec.write_text("# spec\n\nStatus: rascunho\n", encoding="utf-8")
    git(p, "add", "-A")
    draft = git(p, "commit", "-m", "feat: algo\n\nSpec: docs/superpowers/specs/s.md")
    assert draft.returncode != 0
    assert "aprovada" in draft.stderr + draft.stdout
    spec.write_text("# spec\n\nStatus: aprovada pelo dono\n", encoding="utf-8")
    git(p, "add", "-A")
    ok = git(p, "commit", "-m", "feat: algo\n\nSpec: docs/superpowers/specs/s.md")
    assert ok.returncode == 0, ok.stderr


@pytest.mark.skipif(sys.platform == "win32", reason="bit de execucao so existe em Linux/macOS")
def test_hooks_do_scaffold_sao_executaveis(tmp_path):
    p = Path(scaffold_project(str(tmp_path), "exec-app", REPO))
    for hook in (p / ".githooks").iterdir():
        assert os.access(hook, os.X_OK), hook.name


def test_scaffold_nao_sobrescreve(tmp_path):
    (tmp_path / "x").mkdir()
    (tmp_path / "x" / "keep.txt").write_text("a", encoding="utf-8")
    with pytest.raises(FileExistsError):
        scaffold_project(str(tmp_path), "x", REPO)
    assert (tmp_path / "x" / "keep.txt").read_text(encoding="utf-8") == "a"


def test_scaffold_rejeita_slug_fora_da_raiz(tmp_path):
    for bad in ("../x", "a/b", "..", ""):
        with pytest.raises(ValueError):
            scaffold_project(str(tmp_path), bad, REPO)


class Fake:
    def __init__(self):
        self.calls = []

    def __call__(self, agent, prompt, project):
        self.calls.append((agent, prompt, project))
        return 7


@pytest.fixture
def env(tmp_path):
    clock, fake = Clock(), Fake()
    return ProjectCreator(str(tmp_path), REPO, fake, clock=clock), clock, fake, tmp_path


def test_propose_fala_nome_final_e_descricao_mascarada(env):
    c, _, _, _ = env
    r = c.propose("Meu App Legal!", "claude", f"um app com token={SK}")
    assert r["ok"] is True
    assert "meu-app-legal" in r["speech"] and "Confirma" in r["speech"]
    assert SK not in r["speech"]


def test_confirm_cria_e_inicia_uma_vez(env):
    c, _, fake, root = env
    c.propose("Meu App", "claude", "um painel de tarefas")
    r = c.confirm()
    assert r["run_id"] == 7 and Path(r["path"]) == root / "meu-app"
    assert (root / "meu-app" / "AGENTS.md").exists()
    agent, prompt, project = fake.calls[0]
    assert (agent, project) == ("claude", "meu-app")
    assert "um painel de tarefas" in prompt and "docs/superpowers/specs" in prompt and "AGENTS.md" in prompt
    again = c.confirm()
    assert "run_id" not in again and len(fake.calls) == 1


def test_confirm_sem_pendente(env):
    c, _, fake, _ = env
    r = c.confirm()
    assert "run_id" not in r and "nada" in r["speech"].lower() and not fake.calls


def test_expira_em_61s(env):
    c, clock, fake, root = env
    c.propose("app", "claude", "algo")
    clock.t += 61
    r = c.confirm()
    assert "expirou" in r["speech"] and not fake.calls and not (root / "app").exists()


def test_segundo_propose_substitui(env):
    c, _, fake, root = env
    c.propose("um", "claude", "a")
    c.propose("dois", "codex", "b")
    c.confirm()
    assert fake.calls[0][0] == "codex" and fake.calls[0][2] == "dois"
    assert not (root / "um").exists()


def test_projeto_existente_ok_false(env):
    c, _, fake, root = env
    (root / "meu-app").mkdir()
    r = c.propose("Meu App", "claude", "algo")
    assert r["ok"] is False and "já existe" in r["speech"]
    assert "nada" in c.confirm()["speech"].lower() and not fake.calls


def test_entradas_invalidas(env):
    c, _, _, root = env
    assert c.propose("con", "claude", "x")["ok"] is False
    assert c.propose("", "claude", "x")["ok"] is False
    assert c.propose("ok", "naoexiste", "x")["ok"] is False
    assert c.propose("ok", "claude", "  ")["ok"] is False
    assert list(root.iterdir()) == []


def test_nome_malicioso_nunca_sai_da_raiz(env):
    c, _, fake, root = env
    for name in ("../x", "C:\\Windows", "..\\..\\evil"):
        r = c.propose(name, "claude", "algo")
        if r["ok"]:
            res = c.confirm()
            assert Path(res["path"]).resolve().parent == root.resolve()
    assert not (root.parent / "x").exists() and not (root.parent / "evil").exists()


def test_start_run_falho_nao_derruba(tmp_path):
    def boom(*a):
        raise RuntimeError(f"falhou {SK}")

    c = ProjectCreator(str(tmp_path), REPO, boom)
    c.propose("app", "claude", "algo")
    r = c.confirm()
    assert "run_id" not in r and SK not in r["speech"]


def test_cancel(env):
    c, _, fake, _ = env
    assert "Não há" in c.cancel()["speech"]
    c.propose("app", "claude", "algo")
    assert "cancelado" in c.cancel()["speech"].lower()
    assert "run_id" not in c.confirm() and not fake.calls


# ---- M2: pendencia global unica entre ditado e projeto ----
def _linked(tmp_path):
    from heycode.dictation.service import Dictation
    clock, fake = Clock(), Fake()
    runs = []
    d = Dictation(lambda a, t, p: runs.append((a, t, p)) or 9, clock=clock)
    c = ProjectCreator(str(tmp_path), REPO, fake, clock=clock)
    from heycode.projects.routes import make_router
    make_router(c, d, lambda: None)  # a rota liga os dois sem editar server.py
    return c, d, clock, fake, runs


def test_projeto_depois_ditado_confirma_so_o_ditado(tmp_path):
    c, d, _, fake, runs = _linked(tmp_path)
    c.propose("Meu App", "claude", "um painel")
    d.propose("codex", "faca x")
    assert c.has_pending() is False
    assert "run_id" in d.confirm() and runs == [("codex", "faca x", None)]
    assert fake.calls == [] and not (tmp_path / "meu-app").exists()


def test_ditado_depois_projeto_cancela_ditado(tmp_path):
    c, d, _, fake, runs = _linked(tmp_path)
    d.propose("codex", "faca x")
    c.propose("Meu App", "claude", "um painel")
    assert "run_id" not in d.confirm() and runs == []
    assert "run_id" in c.confirm()


def test_projeto_expirado_ha_1h_nao_vence_ditado(tmp_path):
    c, d, clock, fake, runs = _linked(tmp_path)
    c.propose("Meu App", "claude", "um painel")
    clock.t += 3600
    assert c.has_pending() is False
    d.propose("codex", "faca x")
    assert not c.has_pending()
    assert "run_id" in d.confirm() and len(runs) == 1 and fake.calls == []


def test_has_pending_ignora_expirada(env):
    c, clock = env[0], env[1]
    c.propose("Meu App", "claude", "um painel")
    assert c.has_pending() is True
    clock.t += 61
    assert c.has_pending() is False


# ---- B5: git do scaffold com timeout e sem assinatura ----
def test_git_do_scaffold_usa_timeout_e_sem_gpg(tmp_path, monkeypatch):
    import heycode.projects.service as svc
    seen = []
    real = subprocess.run

    def spy(cmd, **kw):
        seen.append((cmd, kw))
        return real(cmd, **kw)

    monkeypatch.setattr(svc.subprocess, "run", spy)
    scaffold_project(str(tmp_path), "ok-proj", REPO)
    assert seen and all(kw.get("timeout") == 30 for _, kw in seen)
    commit = [c for c, _ in seen if "commit" in c][0]
    assert "commit.gpgsign=false" in commit and commit.index("-c") < commit.index("commit")


def test_scaffold_com_timeout_falha_limpo(tmp_path, monkeypatch):
    import heycode.projects.service as svc

    def boom(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, kw.get("timeout"))

    monkeypatch.setattr(svc.subprocess, "run", boom)
    with pytest.raises(subprocess.TimeoutExpired):
        scaffold_project(str(tmp_path), "meio", REPO)
    assert not (tmp_path / "meio").exists()


def test_confirm_com_timeout_fala_erro_sem_pasta(env, monkeypatch):
    import heycode.projects.service as svc
    c, _, fake, root = env

    def boom(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, 30)

    monkeypatch.setattr(svc.subprocess, "run", boom)
    c.propose("Meu App", "claude", "um painel")
    r = c.confirm()
    assert "run_id" not in r and "Não consegui criar" in r["speech"]
    assert fake.calls == [] and not (root / "meu-app").exists()
