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
])
def test_mascara_cada_familia(segredo):
    out = mask_secrets(f"use {segredo} agora")
    assert "[segredo]" in out
    assert "hunter2" not in out and "abcdefghijklmnop" not in out and "IOSFODNN" not in out
    assert "abc123" not in out
    assert out.startswith("use ") and out.endswith(" agora")


def test_texto_normal_intacto():
    assert mask_secrets("lista os arquivos do projeto") == "lista os arquivos do projeto"
    assert mask_secrets("") == ""


def test_varios_segredos():
    out = mask_secrets("a sk-abcdefghijklmnopqrstuvwx b AKIAIOSFODNN7EXAMPLE")
    assert out.count("[segredo]") == 2
