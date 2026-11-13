import os
import sys

import pytest

from heycode import config
from heycode.cli import main
from heycode.config import init_home, load_env_file, rotate_secret

POSIX = pytest.mark.skipif(sys.platform == "win32", reason="permissao 0600 so existe em Linux/macOS")


def test_rotate_gera_novo_segredo_e_backup_com_o_antigo(tmp_path):
    init_home(tmp_path)
    old = load_env_file(tmp_path / "config.env")
    backup = rotate_secret(tmp_path, now=lambda: 1700000000)
    new = load_env_file(tmp_path / "config.env")
    assert new["BRIDGE_SECRET"] != old["BRIDGE_SECRET"] and len(new["BRIDGE_SECRET"]) == 64
    assert new["BRIDGE_CONTROL_SECRET"] == old["BRIDGE_CONTROL_SECRET"] and new["BRIDGE_PIN"] == old["BRIDGE_PIN"]
    assert load_env_file(backup)["BRIDGE_SECRET"] == old["BRIDGE_SECRET"]
    assert "1700000000" in backup.name


@POSIX
def test_backup_tem_permissao_0600(tmp_path):
    init_home(tmp_path)
    backup = rotate_secret(tmp_path)
    assert os.stat(backup).st_mode & 0o777 == 0o600


def test_rotate_do_segredo_de_controle(tmp_path):
    init_home(tmp_path)
    old = load_env_file(tmp_path / "config.env")
    rotate_secret(tmp_path, key="BRIDGE_CONTROL_SECRET")
    new = load_env_file(tmp_path / "config.env")
    assert new["BRIDGE_CONTROL_SECRET"] != old["BRIDGE_CONTROL_SECRET"] and new["BRIDGE_SECRET"] == old["BRIDGE_SECRET"]
    assert new["BRIDGE_SECRET"] != new["BRIDGE_CONTROL_SECRET"]


def test_rotate_sem_config_pede_init(tmp_path):
    with pytest.raises(ValueError, match="init"):
        rotate_secret(tmp_path)


def test_rotate_chave_desconhecida_e_recusada(tmp_path):
    init_home(tmp_path)
    with pytest.raises(ValueError):
        rotate_secret(tmp_path, key="BRIDGE_PIN")


def test_rotate_interrompido_nao_deixa_config_parcial(tmp_path, monkeypatch):
    init_home(tmp_path)
    before = (tmp_path / "config.env").read_text(encoding="utf-8")

    def boom(*a, **k):
        raise OSError("disco cheio")

    monkeypatch.setattr(config.os, "replace", boom)
    with pytest.raises(OSError):
        rotate_secret(tmp_path)
    assert (tmp_path / "config.env").read_text(encoding="utf-8") == before
    assert not list(tmp_path.glob("*.tmp"))


def test_cli_rotate_dry_run_nao_altera_nada(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HEYCODE_HOME", str(tmp_path))
    init_home(tmp_path)
    before = (tmp_path / "config.env").read_text(encoding="utf-8")
    assert main(["rotate-secret"]) == 0
    assert (tmp_path / "config.env").read_text(encoding="utf-8") == before
    assert "--apply" in capsys.readouterr().out


def test_cli_rotate_apply_nao_imprime_o_valor(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HEYCODE_HOME", str(tmp_path))
    init_home(tmp_path)
    monkeypatch.setattr("heycode.service.restart", lambda **kw: False)
    assert main(["rotate-secret", "--apply"]) == 0
    out = capsys.readouterr().out
    assert all(v not in out for v in load_env_file(tmp_path / "config.env").values())
    assert "hooks" in out.lower() and "MCP" in out


def test_cli_rotate_sem_config_falha_com_mensagem(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HEYCODE_HOME", str(tmp_path / "vazio"))
    assert main(["rotate-secret", "--apply"]) == 1
    assert "heycode init" in capsys.readouterr().err


def test_cli_install_service_dry_run(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HEYCODE_HOME", str(tmp_path))
    assert main(["install-service"]) == 0
    assert "dry-run" in capsys.readouterr().out.lower()


def test_cli_uninstall_service_dry_run(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HEYCODE_HOME", str(tmp_path))
    assert main(["uninstall-service"]) == 0
    assert "dry-run" in capsys.readouterr().out.lower()
