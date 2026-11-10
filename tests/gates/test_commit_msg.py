import pytest

from commit_msg import check_commit_message

VALID = "feat: algo\n\nSpec: docs/superpowers/specs/x.md"


@pytest.fixture
def repo(tmp_path):
    d = tmp_path / "docs" / "superpowers" / "specs"
    d.mkdir(parents=True)
    (d / "x.md").write_text("spec", encoding="utf-8")
    (tmp_path / "README.md").write_text("r", encoding="utf-8")
    return tmp_path


def test_feat_sem_trailer_falha(repo, config):
    errs = check_commit_message("feat: algo", repo, config)
    assert errs and any("Spec:" in e for e in errs)


def test_feat_com_trailer_valido_passa(repo, config):
    assert check_commit_message(VALID, repo, config) == []


def test_docs_e_chore_sao_isentos(repo, config):
    assert check_commit_message("docs: x", repo, config) == []
    assert check_commit_message("chore: x", repo, config) == []


def test_trailer_com_spec_inexistente_falha(repo, config):
    msg = "feat: algo\n\nSpec: docs/superpowers/specs/nao.md"
    assert check_commit_message(msg, repo, config)


def test_trailer_com_crlf_passa(repo, config):
    assert check_commit_message(VALID.replace("\n", "\r\n"), repo, config) == []


def test_comentarios_do_git_sao_ignorados(repo, config):
    msg = "# Spec: docs/superpowers/specs/x.md\nfeat: algo"
    assert check_commit_message(msg, repo, config)


def test_merge_e_revert_sao_isentos(repo, config):
    assert check_commit_message("Merge branch 'x'", repo, config) == []
    assert check_commit_message('Revert "feat: x"', repo, config) == []


def test_spec_fora_do_spec_dir_falha(repo, config):
    assert check_commit_message("feat: a\n\nSpec: README.md", repo, config)
    assert check_commit_message(
        "feat: a\n\nSpec: docs/superpowers/specs/../../../README.md", repo, config
    )
    ok = "feat: a\n\nSpec: docs\\superpowers\\specs\\x.md"
    assert check_commit_message(ok, repo, config) == []


def test_tipo_desconhecido_falha(repo, config):
    errs = check_commit_message("foo: x", repo, config)
    assert errs and "feat|fix|docs|chore|test|refactor" in " ".join(errs)


def test_tipo_com_escopo(repo, config):
    assert check_commit_message("feat(x): a", repo, config)
    assert check_commit_message("docs(x): a", repo, config) == []
