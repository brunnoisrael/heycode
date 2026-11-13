import pytest

from heycode import cli, relay_client


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HEYCODE_HOME", str(tmp_path))
    return tmp_path


def test_pair_chama_o_pareamento_e_mostra_o_codigo_de_verificacao(home, monkeypatch, capsys):
    seen = {}

    def fake_pair(relay_url, code, name, home_, *, http, confirm, force=False, **kw):
        seen.update(relay_url=relay_url, code=code, name=name, home=home_, force=force)
        assert confirm("123456") is True
        return "inst-1"

    monkeypatch.setattr(relay_client, "pair_with_relay", fake_pair)
    monkeypatch.setattr("builtins.input", lambda prompt="": "s")
    rc = cli.main(["pair", "abcd2345", "--relay", "https://relay.exemplo", "--name", "notebook"])
    out = capsys.readouterr().out
    assert rc == 0 and "123456" in out and "inst-1" in out
    assert seen["code"] == "ABCD2345" and seen["name"] == "notebook" and seen["force"] is False
    assert seen["relay_url"] == "https://relay.exemplo" and seen["home"] == home


def test_pair_resposta_negativa_cancela(home, monkeypatch):
    def fake_pair(relay_url, code, name, home_, *, http, confirm, **kw):
        assert confirm("123456") is False
        raise relay_client.PairingError("pareamento cancelado")

    monkeypatch.setattr(relay_client, "pair_with_relay", fake_pair)
    monkeypatch.setattr("builtins.input", lambda prompt="": "n")
    assert cli.main(["pair", "ABCD2345", "--relay", "https://relay.exemplo"]) == 1


def test_pair_yes_nao_pergunta(home, monkeypatch):
    def fake_pair(relay_url, code, name, home_, *, http, confirm, **kw):
        assert confirm("123456") is True
        return "inst-1"

    monkeypatch.setattr(relay_client, "pair_with_relay", fake_pair)

    def no_input(prompt=""):
        raise AssertionError("nao deveria perguntar")

    monkeypatch.setattr("builtins.input", no_input)
    assert cli.main(["pair", "ABCD2345", "--relay", "https://relay.exemplo", "--yes"]) == 0


def test_pair_erro_mostra_mensagem_e_sai_com_1(home, monkeypatch, capsys):
    def fake_pair(*a, **k):
        raise relay_client.PairingError("codigo recusado pelo relay (invalid_code)")

    monkeypatch.setattr(relay_client, "pair_with_relay", fake_pair)
    assert cli.main(["pair", "ABCD2345", "--relay", "https://relay.exemplo", "--yes"]) == 1
    assert "invalid_code" in capsys.readouterr().err


def test_pair_exige_relay(home, capsys):
    assert cli.main(["pair", "ABCD2345"]) == 2


def test_connect_sem_pareamento_explica(home, capsys):
    assert cli.main(["connect"]) == 1
    assert "heycode pair" in capsys.readouterr().err


def test_handler_padrao_enfileira_a_instrucao_no_banco_local(home):
    import asyncio

    from heycode.store.db import Store

    store = Store(str(home / "x.db"))
    handler = cli.make_instruction_handler(store)
    out = asyncio.run(handler({"text": "avise o agente", "destination": "proj", "agent": "claude"}))
    assert out["state"] == "done" and "enfileirada" in out["summary"]
    assert store.pop_instruction("claude", "proj")["text"] == "avise o agente"
