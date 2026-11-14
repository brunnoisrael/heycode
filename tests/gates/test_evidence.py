from evidence import check_evidence, main


def test_evidencia_com_gates_e_matriz_aprovados():
    assert check_evidence("success", "success") == []


def test_falha_se_gates_nao_passaram():
    assert check_evidence("failure", "success")


def test_falha_se_matriz_nao_passou():
    assert check_evidence("success", "failure")


def test_ausencia_ou_cancelamento_falham():
    assert check_evidence("", "success")
    assert check_evidence("success", "cancelled")
    assert check_evidence("skipped", "success")


def test_resumo_do_ci_e_gerado_automaticamente(tmp_path, monkeypatch):
    summary = tmp_path / "summary"
    monkeypatch.setenv("GATES_RESULT", "success")
    monkeypatch.setenv("TESTS_RESULT", "success")
    monkeypatch.setenv("GITHUB_SHA", "abc123")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    assert main() == 0
    assert "abc123" in summary.read_text(encoding="utf-8")
    assert "Gates: success. Matriz: success." in summary.read_text(encoding="utf-8")
