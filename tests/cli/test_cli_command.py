import json
import sys

import pytest

from heycode import cli

PY = sys.executable


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HEYCODE_HOME", str(tmp_path))
    monkeypatch.delenv("HA_TOKEN", raising=False)
    return tmp_path


def registry(home):
    path = home / "commands.json"
    return json.loads(path.read_text(encoding="utf-8"))["commands"] if path.exists() else []


def add_script(name="reiniciar app", risk="confirmar", *extra, argv=None, yes=False):
    """As opcoes vao ANTES do `--`: tudo depois dele e argumento do programa."""
    argv = argv or [PY, "-c", "print('oi')"]
    return ["command", "add", name, "--risk", risk, *extra, *(["--yes"] if yes else []), "--script", "--", *argv]


def test_add_script_grava_a_definicao_exata(home, capsys):
    rc = cli.main(
        add_script(
            "reiniciar app", "confirmar", "--alias", "reboot", "--description", "reinicia", "--timeout", "30", "--yes"
        )
    )
    out = capsys.readouterr().out
    assert rc == 0 and "executar reiniciar app" in out
    (cmd,) = registry(home)
    assert cmd["name"] == "reiniciar app" and cmd["type"] == "script" and cmd["risk"] == "confirmar"
    assert cmd["argv"] == [PY, "-c", "print('oi')"] and cmd["aliases"] == ["reboot"] and cmd["timeout"] == 30
    assert cmd["enabled"] is True and cmd["description"] == "reinicia"


def test_argumentos_com_traco_depois_do_separador_sao_preservados(home):
    assert (
        cli.main(add_script("com flags", "confirmar", argv=["programa", "--flag", "-x", "valor com espaco"], yes=True))
        == 0
    )
    assert registry(home)[0]["argv"] == ["programa", "--flag", "-x", "valor com espaco"]


def test_add_mostra_o_que_vai_rodar_e_pergunta_antes_de_gravar(home, monkeypatch, capsys):
    perguntas = []
    monkeypatch.setattr("builtins.input", lambda prompt="": perguntas.append(prompt) or "n")
    assert cli.main(add_script("rodar tarefa", "leitura")) == 1
    out = capsys.readouterr().out
    assert PY in out and "sem pedir confirmação" in out  # leitura roda sem confirmar: o aviso e explicito
    assert perguntas and registry(home) == []  # recusou: nada foi gravado
    monkeypatch.setattr("builtins.input", lambda prompt="": "s")
    assert cli.main(add_script("rodar tarefa", "leitura")) == 0
    assert len(registry(home)) == 1


def test_add_recusa_definicao_invalida_sem_alterar_o_arquivo(home, capsys):
    cli.main(add_script("primeiro", "confirmar", yes=True))
    antes = (home / "commands.json").read_text(encoding="utf-8")
    assert (
        cli.main(["command", "add", "sem argv", "--risk", "confirmar", "--script", "--yes"]) == 1
    )  # nada depois de --script
    assert cli.main(add_script("primeiro", "confirmar", yes=True)) == 1  # nome duplicado
    assert cli.main(add_script("relativo", "confirmar", "--cwd", "pasta/relativa", yes=True)) == 1
    assert cli.main(add_script("lento", "confirmar", "--timeout", "999", yes=True)) == 1
    assert "Erro" in capsys.readouterr().err
    assert (home / "commands.json").read_text(encoding="utf-8") == antes


def test_add_webhook_get_leitura_e_post_exige_risco_maior(home, capsys):
    ok = ["command", "add", "ver luz", "--risk", "leitura", "--webhook", "https://casa.exemplo.com/luz", "--yes"]
    assert cli.main(ok) == 0
    (cmd,) = registry(home)
    assert cmd["type"] == "webhook" and cmd["method"] == "GET" and cmd["url"] == "https://casa.exemplo.com/luz"
    bad = [
        "command",
        "add",
        "acender",
        "--risk",
        "leitura",
        "--webhook",
        "https://casa.exemplo.com/luz",
        "--method",
        "POST",
        "--yes",
    ]
    assert cli.main(bad) == 1 and "leitura" in capsys.readouterr().err
    assert (
        cli.main(
            ["command", "add", "http externo", "--risk", "confirmar", "--webhook", "http://casa.exemplo.com/x", "--yes"]
        )
        == 1
    )


def test_webhook_cabecalho_por_referencia_exige_a_variavel_e_nunca_imprime_valor(home, capsys):
    base = [
        "command",
        "add",
        "acender",
        "--risk",
        "confirmar",
        "--webhook",
        "https://casa.exemplo.com/luz",
        "--method",
        "POST",
        "--body",
        '{"ligar": true}',
        "--header",
        "Authorization: env:HA_TOKEN",
        "--header",
        "X-Literal: valor-literal-secreto",
        "--yes",
    ]
    assert cli.main(base) == 1 and "HA_TOKEN" in capsys.readouterr().err  # a variavel nao existe no config.env
    (home / "config.env").write_text("HA_TOKEN=Bearer abc123\n", encoding="utf-8")
    assert cli.main(base) == 0
    out = capsys.readouterr().out
    assert "valor-literal-secreto" not in out and "abc123" not in out and "env:HA_TOKEN" in out
    cmd = registry(home)[0]
    assert cmd["headers"] == {"Authorization": "env:HA_TOKEN", "X-Literal": "valor-literal-secreto"}
    assert cmd["body"] == {"ligar": True}


def test_body_invalido_e_recusado(home, capsys):
    argv = [
        "command",
        "add",
        "x1",
        "--risk",
        "confirmar",
        "--webhook",
        "https://a.exemplo.com/",
        "--method",
        "POST",
        "--body",
        "{nao json",
        "--yes",
    ]
    assert cli.main(argv) == 1 and registry(home) == []


def test_list_mostra_tipo_risco_e_estado(home, capsys):
    assert cli.main(["command", "list"]) == 0 and "Nenhum comando" in capsys.readouterr().out
    cli.main(add_script("reiniciar app", "confirmar", "--yes"))
    cli.main(add_script("ver disco", "leitura", "--yes"))
    cli.main(["command", "disable", "ver disco"])
    cli.main(["command", "list"])
    out = capsys.readouterr().out
    assert "reiniciar app" in out and "confirmar" in out and "ver disco" in out and "desligado" in out


def test_enable_disable_e_remove(home, capsys):
    cli.main(add_script("reiniciar app", "confirmar", "--yes"))
    assert cli.main(["command", "disable", "Reiniciar  App"]) == 0 and registry(home)[0]["enabled"] is False
    assert cli.main(["command", "enable", "reiniciar app"]) == 0 and registry(home)[0]["enabled"] is True
    assert cli.main(["command", "enable", "nao existe"]) == 1
    assert cli.main(["command", "remove", "reiniciar app", "--yes"]) == 0 and registry(home) == []
    assert cli.main(["command", "remove", "reiniciar app", "--yes"]) == 1


def test_remove_pede_confirmacao(home, monkeypatch):
    cli.main(add_script("reiniciar app", "confirmar", "--yes"))
    monkeypatch.setattr("builtins.input", lambda prompt="": "n")
    assert cli.main(["command", "remove", "reiniciar app"]) == 1 and len(registry(home)) == 1


def test_test_roda_localmente_com_confirmacao_no_terminal(home, monkeypatch, capsys, tmp_path):
    marker = tmp_path / "t.txt"
    cli.main(add_script("gravar", "pin", argv=[PY, "-c", f"open({str(marker)!r}, 'w').write('x')"], yes=True))
    monkeypatch.setattr("builtins.input", lambda prompt="": "n")
    assert cli.main(["command", "test", "gravar"]) == 1 and not marker.exists()
    monkeypatch.setattr("builtins.input", lambda prompt="": "s")
    assert cli.main(["command", "test", "gravar"]) == 0 and marker.exists()  # quem esta no terminal e o dono: sem PIN
    assert "terminou com sucesso" in capsys.readouterr().out


def test_test_de_comando_inexistente_falha(home, capsys):
    assert cli.main(["command", "test", "nada"]) == 1


def test_registro_corrompido_nao_e_sobrescrito(home, capsys):
    (home / "commands.json").write_text("{ corrompido", encoding="utf-8")
    assert cli.main(add_script("novo", "confirmar", "--yes")) == 1
    assert (home / "commands.json").read_text(encoding="utf-8") == "{ corrompido"
    assert "Erro" in capsys.readouterr().err


@pytest.mark.skipif(sys.platform == "win32", reason="permissoes POSIX")
def test_arquivo_gravado_com_permissao_restrita(home):
    import os
    import stat

    cli.main(add_script("reiniciar app", "confirmar", "--yes"))
    assert stat.S_IMODE(os.stat(home / "commands.json").st_mode) == 0o600
