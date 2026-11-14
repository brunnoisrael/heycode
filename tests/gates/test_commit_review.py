import json

import pytest
from commit_review import check_review, main


def status(login="review-bot", state="success", context="heycode-review"):
    return {"creator": {"login": login}, "state": state, "context": context}


def test_revisao_independente_aprovada():
    assert check_review([status()], "review-bot", "author") == []


def test_revisor_ou_autor_ausente_falha():
    assert check_review([status()], "", "author")
    assert check_review([status()], "review-bot", "")


def test_revisor_nao_pode_ser_o_autor():
    assert check_review([status()], "review-bot", "review-bot")


def test_outro_usuario_ou_contexto_nao_aprova():
    assert check_review([status(login="intruso")], "review-bot", "author")
    assert check_review([status(context="outro")], "review-bot", "author")


def test_ultima_revisao_do_revisor_prevalece():
    assert check_review([status(state="failure"), status()], "review-bot", "author")
    assert check_review([status(), status(state="failure")], "review-bot", "author") == []


def test_ausencia_ou_status_malformado_falha():
    assert check_review([], "review-bot", "author")
    assert check_review([{"context": "heycode-review", "creator": None}], "review-bot", "author")


def test_consulta_github_ao_sha_exato(monkeypatch):
    sha = "a" * 40
    monkeypatch.setenv("GITHUB_REPOSITORY", "org/repo")
    monkeypatch.setenv("HEAD_SHA", sha)
    monkeypatch.setenv("INDEPENDENT_REVIEWER", "review-bot")
    calls = []

    def api(args, **kwargs):
        calls.append(args)
        if "statuses?" in args[-1]:
            return json.dumps([[status()]])
        return json.dumps({"author": {"login": "author"}})

    monkeypatch.setattr("commit_review.subprocess.check_output", api)
    assert main() == 0
    assert all(sha in call[-1] for call in calls)
    assert "--paginate" in calls[1]


def test_consulta_sem_aprovacao_falha(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_REPOSITORY", "org/repo")
    monkeypatch.setenv("HEAD_SHA", "a" * 40)
    monkeypatch.setenv("INDEPENDENT_REVIEWER", "review-bot")
    monkeypatch.setattr(
        "commit_review.subprocess.check_output",
        lambda args, **kwargs: json.dumps([[]] if "statuses?" in args[-1] else {"author": None}),
    )
    assert main() == 1
    assert "falha fechada" in capsys.readouterr().err


def test_rejeita_sha_invalido_antes_da_consulta(monkeypatch):
    monkeypatch.setenv("GITHUB_REPOSITORY", "org/repo")
    monkeypatch.setenv("HEAD_SHA", "invalid")
    with pytest.raises(ValueError, match="SHA invalido"):
        main()
