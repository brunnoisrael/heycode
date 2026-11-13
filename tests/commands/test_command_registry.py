import json
import sys

import pytest

from heycode.commands import (
    MAX_COMMANDS,
    CommandError,
    definition_hash,
    load,
    match_command,
    parse_registry,
    save,
    summary,
)


def script(name="reiniciar app", **over):
    d = {"name": name, "type": "script", "risk": "confirmar", "argv": [sys.executable, "-c", "print(1)"]}
    d.update(over)
    return d


def hook(name="acender luz", **over):
    d = {"name": name, "type": "webhook", "risk": "confirmar", "url": "https://casa.exemplo.com/luz", "method": "POST"}
    d.update(over)
    return d


def reg(*cmds):
    return {"version": 1, "commands": list(cmds)}


def bad(*cmds, env=None):
    with pytest.raises(CommandError):
        parse_registry(reg(*cmds), env or {})


def test_registro_valido_de_script_e_webhook(tmp_path):
    cmds = parse_registry(reg(script(cwd=str(tmp_path), timeout=30, aliases=["reboot"]), hook()), {})
    s, w = cmds
    assert (s.type, s.risk, s.timeout, s.enabled, s.aliases) == ("script", "confirmar", 30, True, ("reboot",))
    assert (w.type, w.method, w.url) == ("webhook", "POST", "https://casa.exemplo.com/luz")


def test_vazio_e_arquivo_ausente_sao_lista_vazia(tmp_path):
    assert parse_registry({"version": 1, "commands": []}, {}) == []
    assert load(tmp_path / "nao-existe.json") == []


def test_versao_e_campos_desconhecidos_sao_recusados():
    with pytest.raises(CommandError):
        parse_registry({"version": 2, "commands": []}, {})
    bad(script(shell=True))  # nada de "shell": erro de digitacao nao vira execucao
    bad(script(comando="rm -rf /"))
    with pytest.raises(CommandError):
        parse_registry({"version": 1, "commands": [], "extra": 1}, {})


@pytest.mark.parametrize(
    "patch",
    [
        {"argv": []},
        {"argv": [""]},
        {"argv": "echo oi"},  # string, nao lista: seria shell
        {"argv": ["a"] * 33},
        {"argv": ["a", 5]},
        {"cwd": "relativo/pasta"},
        {"cwd": "/pasta/que/nao/existe/mesmo"},
        {"timeout": 0},
        {"timeout": 301},
        {"timeout": "60"},
        {"env_pass": ["minuscula"]},
        {"env_pass": ["COM ESPACO"]},
        {"url": "https://x.example.com"},  # campo de webhook em script
        {"risk": "livre"},
        {"enabled": "sim"},
        {"name": "a"},
        {"name": "x" * 41},
        {"aliases": ["um", "dois", "tres", "quatro", "cinco", "seis"]},
        {"description": "d" * 201},
    ],
)
def test_script_invalido_e_recusado(patch):
    bad(script(**patch))


@pytest.mark.parametrize(
    "patch",
    [
        {"url": "http://casa.exemplo.com/luz"},  # sem TLS fora do localhost
        {"url": "ftp://casa.exemplo.com"},
        {"url": "https://"},
        {"url": "https://user:senha@casa.exemplo.com/"},
        {"url": "https://casa.exemplo.com/luz#x"},
        {"method": "DELETE"},
        {"method": "POST", "risk": "leitura"},  # muda estado: nunca leitura
        {"method": "GET", "body": {"a": 1}},
        {"body": "texto"},
        {"timeout": 31},
        {"headers": {"Authorization": "env:TOKEN_AUSENTE"}},
        {"headers": {"bad header": "x"}},
        {"headers": {"X-A": 5}},
        {"argv": ["a"]},  # campo de script em webhook
    ],
)
def test_webhook_invalido_e_recusado(patch):
    bad(hook(**patch))


def test_webhook_aceita_localhost_sem_tls_get_leitura_e_header_por_referencia():
    parse_registry(reg(hook(url="http://127.0.0.1:8123/api", method="GET", risk="leitura")), {})
    parse_registry(reg(hook(url="http://localhost/x", method="GET", risk="leitura")), {})
    ok = parse_registry(reg(hook(headers={"Authorization": "env:HA_TOKEN"})), {"HA_TOKEN": "valor"})
    assert ok[0].headers == {"Authorization": "env:HA_TOKEN"}


def test_nome_ou_apelido_duplicado_como_a_alexa_ouve_e_recusado():
    bad(script("Reiniciar app"), script("reiniciar   APP!"))
    bad(script("um nome"), script("outro nome", aliases=["Um Nome"]))
    bad(script("ola", aliases=["mundo"]), script("mundo"))


def test_limite_de_comandos():
    cmds = [script(f"comando {i:03d}") for i in range(MAX_COMMANDS + 1)]
    bad(*cmds)
    parse_registry(reg(*cmds[:MAX_COMMANDS]), {})


def test_resumo_nunca_traz_argv_url_cabecalho_ou_corpo():
    cmds = parse_registry(
        reg(script(description="reinicia o app"), hook(headers={"Authorization": "env:T"}, body={"segredo": "x"})),
        {"T": "v"},
    )
    texto = json.dumps([summary(c) for c in cmds])
    for proibido in ("print(1)", "casa.exemplo.com", "Authorization", "segredo", "env:T", sys.executable):
        assert proibido not in texto
    assert summary(cmds[0]) == {
        "name": "reiniciar app",
        "aliases": [],
        "type": "script",
        "risk": "confirmar",
        "enabled": True,
        "description": "reinicia o app",
    }


def test_hash_muda_quando_qualquer_parte_da_definicao_muda():
    a, b = parse_registry(reg(script(), script("outro nome", argv=[sys.executable, "-c", "print(2)"])), {})
    assert definition_hash(a) != definition_hash(b)
    assert definition_hash(a) == definition_hash(parse_registry(reg(script()), {})[0])
    c = parse_registry(reg(script(risk="leitura")), {})[0]
    assert definition_hash(a) != definition_hash(c)


def test_salvar_e_carregar_e_atomico_e_preserva_o_conteudo(tmp_path):
    path = tmp_path / "commands.json"
    save(path, [script(), hook()])
    assert [c.name for c in load(path)] == ["reiniciar app", "acender luz"]
    assert not list(tmp_path.glob("*.tmp"))
    path.write_text("{ isto nao e json", encoding="utf-8")
    with pytest.raises(CommandError):
        load(path)


def test_casamento_usa_so_comandos_ligados_e_recusa_empate():
    cmds = parse_registry(
        reg(
            script("rodar testes api"),
            script("rodar testes app"),
            script("subir deploy"),
            script("apagar tudo", enabled=False),
        ),
        {},
    )
    assert match_command("subir deploy", cmds)[0].name == "subir deploy"
    assert match_command("rodar testes ap", cmds) == (None, "ambiguous")
    assert match_command("apagar tudo", cmds) == (None, "none")  # desligado nunca casa
    assert match_command("fazer cafe", cmds) == (None, "none")
