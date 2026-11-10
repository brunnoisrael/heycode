import pytest

from bridge.policy.redact import mask_secrets


@pytest.mark.parametrize("segredo", [
    "sk-abcdefghijklmnopqrstuvwx",
    "sk-ant-api03-abcdefghijklmnopqrstuvwx",
    "ghp_abcdefghijklmnopqrstuvwxyz0123456789",
    "AKIAIOSFODNN7EXAMPLE",
    "password=hunter2",
    "PASSWORD: hunter2",
    "senha=abc123",
    "OPENAI_API_KEY=sk-proj-x",
    "GITHUB_TOKEN=ghp_x",
    "DB_PASSWORD=x",
    "Authorization: Bearer abc.def.ghi",
    "https://user:senha@host/x",
    "mysql -pSenha123",
    "github_pat_11ABCDEFG0abcdefghijklmnop",
    "ASIAIOSFODNN7EXAMPLE",
    "xoxb-123456789012-abcdef",
    "xoxp-123456789012-abcdef",
    "MY_SECRET: valorsecreto",
    "db_pwd=zzz",
])
def test_mascara_cada_familia(segredo):
    out = mask_secrets(f"use {segredo} agora")
    assert "[segredo]" in out
    assert "hunter2" not in out and "abcdefghijklmnop" not in out and "IOSFODNN" not in out
    assert "abc123" not in out
    for vazou in ("proj-x", "ghp_x", "abc.def.ghi", "Senha123", "user:senha", "valorsecreto", "zzz", "xoxb-1", "xoxp-1"):
        assert vazou not in out
    assert "DB_PASSWORD=x" not in out
    assert out.startswith("use ") and out.endswith(" agora")


def test_texto_normal_intacto():
    assert mask_secrets("lista os arquivos do projeto") == "lista os arquivos do projeto"
    assert mask_secrets("") == ""


@pytest.mark.parametrize("texto", [
    "o passo: listar arquivos", "rode pytest -p no:cacheprovider", "aider --no-pretty --yes-always",
    "visite https://host/x?a=1", "a chave do problema: simples", "ls -la",
])
def test_texto_comum_intacto(texto):
    assert mask_secrets(texto) == texto


def test_varios_segredos():
    out = mask_secrets("a sk-abcdefghijklmnopqrstuvwx b AKIAIOSFODNN7EXAMPLE")
    assert out.count("[segredo]") == 2
