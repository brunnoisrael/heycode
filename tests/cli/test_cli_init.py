import importlib
import sys

from heycode.cli import main
from heycode.config import load_env_file


def test_init_cria_config_e_nao_imprime_segredos(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HEYCODE_HOME", str(tmp_path / "h"))
    assert main(["init"]) == 0
    out = capsys.readouterr().out
    values = load_env_file(tmp_path / "h" / "config.env")
    assert "BRIDGE_SECRET" in out and str(tmp_path / "h") in out
    assert all(v not in out for v in values.values())


def test_init_repetido_informa_o_que_ja_existe(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HEYCODE_HOME", str(tmp_path / "h"))
    main(["init"])
    capsys.readouterr()
    assert main(["init"]) == 0
    assert "já existe" in capsys.readouterr().out


def test_init_import_legacy_copia_antes_de_gerar(tmp_path, monkeypatch, capsys):
    clone = tmp_path / "clone"
    (clone / "bridge").mkdir(parents=True)
    (clone / "bridge" / "bridge.db").write_bytes(b"db")
    (clone / ".env").write_text("BRIDGE_SECRET=" + "d" * 64 + "\n", encoding="utf-8")
    monkeypatch.setenv("HEYCODE_HOME", str(tmp_path / "h"))
    assert main(["init", "--import-legacy", str(clone)]) == 0
    assert load_env_file(tmp_path / "h" / "config.env")["BRIDGE_SECRET"] == "d" * 64
    assert (tmp_path / "h" / "heycode.db").read_bytes() == b"db"
    assert "importado" in capsys.readouterr().out


def test_init_import_legacy_com_pasta_inexistente_falha(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HEYCODE_HOME", str(tmp_path / "h"))
    assert main(["init", "--import-legacy", str(tmp_path / "nao-existe")]) == 1
    assert "não encontrada" in capsys.readouterr().err


def test_app_usa_o_banco_do_diretorio_do_usuario(tmp_path, monkeypatch):
    monkeypatch.setenv("HEYCODE_HOME", str(tmp_path / "h"))
    monkeypatch.delenv("BRIDGE_DB", raising=False)
    monkeypatch.setenv("BRIDGE_SECRET", "a" * 40)
    monkeypatch.setenv("BRIDGE_CONTROL_SECRET", "c" * 40)
    monkeypatch.setenv("BRIDGE_PIN", "1234")
    if "heycode.app" in sys.modules:
        app = importlib.reload(sys.modules["heycode.app"])
    else:
        app = importlib.import_module("heycode.app")
    try:
        assert app.DB_PATH == str(tmp_path / "h" / "heycode.db")
    finally:
        app.store.close()
