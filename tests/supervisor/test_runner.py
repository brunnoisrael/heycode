import pytest

from bridge.supervisor.runner import build_command


def test_codex_auto():
    assert build_command("codex", "oi", "C:/p", "auto", "out.txt", {"codex": ["codex"]}) == [
        "codex", "exec", "-C", "C:/p", "-s", "danger-full-access", "--json", "-o", "out.txt",
        "--skip-git-repo-check", "oi"]


@pytest.mark.parametrize("mode", ["manual", "decisoes"])
def test_codex_restrito(mode):
    cmd = build_command("codex", "oi", "C:/p", mode, "out.txt", {"codex": ["codex"]})
    assert cmd[cmd.index("-s") + 1] == "workspace-write"


def test_claude_auto():
    assert build_command("claude", "oi", "C:/p", "auto", "o", {"claude": ["claude"]}) == [
        "claude", "-p", "oi", "--output-format", "json", "--dangerously-skip-permissions"]


@pytest.mark.parametrize("mode", ["manual", "decisoes"])
def test_claude_restrito(mode):
    assert build_command("claude", "oi", "C:/p", mode, "o", {"claude": ["claude"]}) == [
        "claude", "-p", "oi", "--output-format", "json"]


@pytest.mark.parametrize("mode", ["auto", "manual", "decisoes"])
def test_aider_igual_em_todos_os_modos(mode):
    assert build_command("aider", "oi", "C:/p", mode, "o", {"aider": ["aider"]}) == [
        "aider", "--message", "oi", "--yes-always", "--no-pretty", "--no-auto-commits"]


def test_agente_desconhecido():
    with pytest.raises(ValueError):
        build_command("gemini", "oi", ".", "auto", "o")


def test_mapa_injetado_com_prefixo_multiplo():
    cmd = build_command("claude", "oi", ".", "manual", "o", {"claude": ["python", "-c", "x"]})
    assert cmd[:3] == ["python", "-c", "x"]
