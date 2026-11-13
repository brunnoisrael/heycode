import pytest
from commit_msg import check_commit_message
from spec_status import check_spec_approved


def _spec(tmp_path, text):
    p = tmp_path / "spec.md"
    p.write_text(text, encoding="utf-8")
    return p


def test_spec_aprovada_passa(tmp_path):
    p = _spec(tmp_path, "# T\n\nData: 2026-11-13. Status: aprovada pelo dono em 2026-11-13.\n")
    assert check_spec_approved(p) == []


def test_status_aprovado_com_capitalizacao_diferente_passa(tmp_path):
    assert check_spec_approved(_spec(tmp_path, "# T\n\nStatus: Aprovada\n")) == []


def test_spec_rascunho_falha(tmp_path):
    p = _spec(tmp_path, "# T\n\nData: 2026-11-09. Status: rascunho aguardando aprovação.\n")
    assert check_spec_approved(p)


def test_spec_sem_status_falha(tmp_path):
    assert check_spec_approved(_spec(tmp_path, "# T\n\nsem campo de status\n"))


def test_nao_aprovada_falha(tmp_path):
    assert check_spec_approved(_spec(tmp_path, "# T\n\nStatus: não aprovada\n"))


def test_status_depois_da_linha_10_nao_conta(tmp_path):
    text = "# T\n" + "x\n" * 12 + "Status: aprovada\n"
    assert check_spec_approved(_spec(tmp_path, text))


def test_arquivo_ausente_falha(tmp_path):
    assert check_spec_approved(tmp_path / "nao-existe.md")


@pytest.fixture
def repo(tmp_path):
    d = tmp_path / "docs" / "superpowers" / "specs"
    d.mkdir(parents=True)
    (d / "rascunho.md").write_text("# T\n\nStatus: rascunho\n", encoding="utf-8")
    (d / "ok.md").write_text("# T\n\nStatus: aprovada pelo dono\n", encoding="utf-8")
    return tmp_path


def test_commit_feat_com_spec_rascunho_falha(repo, config):
    msg = "feat: a\n\nSpec: docs/superpowers/specs/rascunho.md"
    errs = check_commit_message(msg, repo, config)
    assert errs and any("aprovada" in e for e in errs)


def test_commit_feat_com_spec_aprovada_passa(repo, config):
    msg = "feat: a\n\nSpec: docs/superpowers/specs/ok.md"
    assert check_commit_message(msg, repo, config) == []


def test_commit_docs_nao_exige_spec_aprovada(repo, config):
    assert check_commit_message("docs: a", repo, config) == []
