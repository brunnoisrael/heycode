import json

import pytest

from heycode import cli, relay_client


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HEYCODE_HOME", str(tmp_path))
    return tmp_path


def paired(home):
    (home / "relay.json").write_text(json.dumps({"relay_url": "https://r.example", "installation_id": "i1"}))


def test_auto_comeca_desligado(home):
    paired(home)
    assert relay_client.auto_allowed(home) is False
    assert relay_client.auto_allowed(home / "nao-existe") is False


def test_relay_auto_on_liga_e_off_desliga(home, capsys):
    paired(home)
    assert cli.main(["relay-auto", "on", "--yes"]) == 0
    assert relay_client.auto_allowed(home) is True
    assert json.loads((home / "relay.json").read_text())["installation_id"] == "i1"  # nao perde o resto
    assert cli.main(["relay-auto", "off"]) == 0
    assert relay_client.auto_allowed(home) is False
    assert "automático" in capsys.readouterr().out


def test_relay_auto_on_pede_confirmacao_no_computador(home, monkeypatch):
    paired(home)
    monkeypatch.setattr("builtins.input", lambda prompt="": "n")
    assert cli.main(["relay-auto", "on"]) == 1
    assert relay_client.auto_allowed(home) is False
    monkeypatch.setattr("builtins.input", lambda prompt="": "sim")
    assert cli.main(["relay-auto", "on"]) == 0
    assert relay_client.auto_allowed(home) is True


def test_relay_auto_exige_computador_pareado(home, capsys):
    assert cli.main(["relay-auto", "on", "--yes"]) == 1
    assert "heycode pair" in capsys.readouterr().err


def test_connect_monta_executor_so_com_segredo_de_controle(home, monkeypatch):
    from heycode import config, relay_executor

    monkeypatch.delenv("BRIDGE_CONTROL_SECRET", raising=False)
    assert cli._make_bridge_executor(home, config, relay_executor) is None  # sem config.env
    (home / "config.env").write_text("BRIDGE_CONTROL_" + "SECRET" + "=" + "valor-local-de-teste\n")
    ex = cli._make_bridge_executor(home, config, relay_executor)
    assert isinstance(ex, relay_executor.BridgeExecutor)
