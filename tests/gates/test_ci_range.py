import subprocess
from pathlib import Path

import pytest
from ci_range import changed_files, check_agent_review, check_protected, check_range
from workflow_pins import check_workflow_pins

ROOT = Path(__file__).resolve().parents[2]
SPEC = "docs/superpowers/specs/s.md"


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=a@b.c", "-c", "user.name=t", *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q", "-b", "main")
    spec = tmp_path / SPEC
    spec.parent.mkdir(parents=True)
    spec.write_text("# S\n\nStatus: aprovada\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("r\n", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "chore: base")
    return tmp_path


def commit(repo, msg, files):
    for rel, text in files.items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "--no-verify", "-m", msg)


def run(repo, config):
    return check_range("main", "HEAD", config, repo)


def start(repo):
    git(repo, "checkout", "-q", "-b", "pr")


def test_commit_sem_trailer_no_meio_do_pr_falha(repo, config):
    start(repo)
    commit(repo, "docs: ok", {"docs/a.md": "a\n"})
    commit(repo, "feat: sem trailer", {"bridge/a.py": "x = 1\n", "tests/test_a.py": "t = 1\n"})
    commit(repo, "docs: outro", {"docs/b.md": "b\n"})
    errs = run(repo, config)
    assert errs and any("Spec:" in e for e in errs)


def test_no_verify_nao_escapa_do_ci(repo, config):
    # commit() usa --no-verify; o CI repete a checagem e pega o commit ruim.
    start(repo)
    commit(repo, "feat: ruim", {"bridge/a.py": "x = 1\n"})
    assert run(repo, config)


def test_pr_valido_passa(repo, config):
    start(repo)
    msg = f"feat: bom\n\nSpec: {SPEC}"
    commit(repo, msg, {"bridge/a.py": "x = 1\n", "tests/test_a.py": "t = 1\n"})
    assert run(repo, config) == []


def test_spec_rascunho_no_pr_falha(repo, config):
    start(repo)
    (repo / SPEC).write_text("# S\n\nStatus: rascunho\n", encoding="utf-8")
    commit(repo, f"feat: x\n\nSpec: {SPEC}", {"bridge/a.py": "x\n", "tests/test_a.py": "t\n"})
    assert any("aprovada" in e for e in run(repo, config))


def test_g3_arquitetura_sem_adr_no_commit_falha(repo, config):
    start(repo)
    commit(repo, f"feat: x\n\nSpec: {SPEC}", {"bridge/policy/engine.py": "x\n", "tests/test_e.py": "t\n"})
    assert any("ADR" in e for e in run(repo, config))


def test_g3_com_adr_novo_passa(repo, config):
    start(repo)
    files = {"bridge/policy/engine.py": "x\n", "tests/test_e.py": "t\n", "docs/adr/0100-x.md": "# x\n"}
    commit(repo, f"feat: x\n\nSpec: {SPEC}", files)
    assert run(repo, config) == []


def test_g4_feat_sem_teste_falha_no_ci(repo, config):
    start(repo)
    commit(repo, f"feat: x\n\nSpec: {SPEC}", {"bridge/a.py": "x\n"})
    assert any("G4:" in e for e in run(repo, config))


def test_g12_pr_grande_falha(repo, config):
    start(repo)
    big = "x = 1\n" * 401
    commit(repo, f"feat: x\n\nSpec: {SPEC}", {"bridge/a.py": big, "tests/test_a.py": "t\n"})
    assert any(e.startswith("G12") for e in run(repo, config))


def test_segredo_adicionado_e_removido_no_pr_continua_detectado(repo):
    from secret_scan import scan_range

    start(repo)
    fake = "BRIDGE_SECRET=" + "k9Xv2LmQ8rTz4WnB7yHc1JdF5gSa3PeU"
    commit(repo, "chore: x", {".env.exemplo": fake + "\n"})
    commit(repo, "chore: y", {".env.exemplo": "BRIDGE_SECRET=<seu-segredo>\n"})
    assert scan_range("main", "HEAD", str(repo))


def test_commits_de_merge_sao_ignorados(repo, config):
    start(repo)
    commit(repo, "docs: a", {"docs/a.md": "a\n"})
    assert run(repo, config) == []


def test_alteracao_em_gates_json_exige_aprovacao_humana(config):
    errs = check_protected(["scripts/gates/gates.json"], approvers=set(), author="bot", config=config)
    assert errs and any("G11" in e for e in errs)


def test_alteracao_em_workflows_exige_aprovacao_humana(config):
    assert check_protected([".github/workflows/ci.yml"], approvers=set(), author="bot", config=config)


def test_autor_nao_aprova_o_proprio_pr(config):
    cfg = {**config, "human_owners": ["dono"]}
    assert check_protected(["AGENTS.md"], approvers={"dono"}, author="dono", config=cfg)


def test_dono_diferente_do_autor_aprova(config):
    cfg = {**config, "human_owners": ["dono"]}
    assert check_protected(["AGENTS.md"], approvers={"dono"}, author="robo", config=cfg) == []


def test_aprovador_fora_da_lista_de_donos_nao_vale(config):
    cfg = {**config, "human_owners": ["dono"]}
    assert check_protected(["AGENTS.md"], approvers={"qualquer"}, author="robo", config=cfg)


def test_sem_donos_configurados_falha_fechado(config):
    cfg = {**config, "human_owners": []}
    errs = check_protected(["AGENTS.md"], approvers={"dono"}, author="robo", config=cfg)
    assert errs and any("human_owners" in e for e in errs)


def test_caminho_sensivel_exige_aprovacao_humana(config):
    assert check_protected(["bridge/policy/engine.py"], approvers=set(), author="robo", config=config)


def test_pr_sem_caminho_protegido_nao_exige_aprovacao(config):
    assert check_protected(["README.md", "tests/a.py"], approvers=set(), author="robo", config=config) == []


def test_agent_review_exige_aprovacao_do_bot_no_head(config):
    reviews = [{"user": "revisor-bot", "state": "APPROVED", "commit": "abc"}]
    assert check_agent_review(reviews, "abc", "revisor-bot", "robo") == []


def test_agent_review_de_commit_antigo_nao_vale():
    reviews = [{"user": "revisor-bot", "state": "APPROVED", "commit": "velho"}]
    assert check_agent_review(reviews, "novo", "revisor-bot", "robo")


def test_agent_review_sem_bot_configurado_falha_fechado():
    assert check_agent_review([], "abc", "", "robo")


def test_agent_review_do_proprio_autor_nao_vale():
    reviews = [{"user": "robo", "state": "APPROVED", "commit": "abc"}]
    assert check_agent_review(reviews, "abc", "robo", "robo")


def test_agent_review_pedindo_mudancas_bloqueia():
    reviews = [
        {"user": "revisor-bot", "state": "APPROVED", "commit": "abc"},
        {"user": "revisor-bot", "state": "CHANGES_REQUESTED", "commit": "abc"},
    ]
    assert check_agent_review(reviews, "abc", "revisor-bot", "robo")


def test_acao_com_tag_movel_falha():
    assert check_workflow_pins("steps:\n  - uses: actions/checkout@v4\n")


def test_acao_fixada_por_hash_passa():
    h = "3d3c42e5aac5ba805825da76410c181273ba90b1"
    assert check_workflow_pins(f"steps:\n  - uses: actions/checkout@{h} # v7.0.1\n") == []


def test_acao_local_e_ignorada():
    assert check_workflow_pins("steps:\n  - uses: ./.github/actions/x\n") == []


def test_workflows_do_repositorio_estao_fixados():
    for wf in (ROOT / ".github" / "workflows").glob("*.yml"):
        assert check_workflow_pins(wf.read_text(encoding="utf-8")) == [], wf.name


def test_mover_arquivo_protegido_para_fora_nao_esconde_a_mudanca(repo, config):
    commit(repo, "chore: base gates", {"scripts/gates/x.py": "x = 1" + chr(10) * 30})
    git(repo, "checkout", "-q", "-b", "pr2")
    (repo / "outro").mkdir()
    git(repo, "mv", "scripts/gates/x.py", "outro/x.py")
    git(repo, "commit", "-q", "--no-verify", "-m", "chore: mover")
    files = changed_files(repo, "main", "HEAD")
    assert "scripts/gates/x.py" in files
    errs = check_protected(files, approvers=set(), author="robo", config=config)
    assert errs
