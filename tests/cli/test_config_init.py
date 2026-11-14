import os
import sys

import pytest

from heycode.config import apply_env, import_legacy, init_home, load_env_file

POSIX = pytest.mark.skipif(sys.platform == "win32", reason="permissao 0600 so existe em Linux/macOS")
KEYS = ("BRIDGE_SECRET", "BRIDGE_CONTROL_SECRET", "BRIDGE_PIN")


def test_load_env_file_le_pares_ignora_comentarios_e_aspas(tmp_path):
    f = tmp_path / "c.env"
    f.write_text("# x\n\nA=1\nB=\"dois\"\nC='tres'\nsem_igual\n", encoding="utf-8")
    assert load_env_file(f) == {"A": "1", "B": "dois", "C": "tres"}


def test_load_env_file_ausente_devolve_vazio(tmp_path):
    assert load_env_file(tmp_path / "nao.env") == {}


def test_apply_env_nao_sobrescreve_variavel_ja_definida():
    environ = {"A": "real"}
    apply_env({"A": "arquivo", "B": "novo"}, environ)
    assert environ == {"A": "real", "B": "novo"}


def test_init_cria_segredos_distintos_de_64_hex_e_pin_de_6_digitos(tmp_path):
    result = init_home(tmp_path / "h")
    values = load_env_file(tmp_path / "h" / "config.env")
    assert sorted(result["created"]) == sorted(KEYS) and result["kept"] == []
    assert len(values["BRIDGE_SECRET"]) == 64 and int(values["BRIDGE_SECRET"], 16) >= 0
    assert len(values["BRIDGE_CONTROL_SECRET"]) == 64
    assert values["BRIDGE_SECRET"] != values["BRIDGE_CONTROL_SECRET"]
    assert len(values["BRIDGE_PIN"]) == 6 and values["BRIDGE_PIN"].isdigit()


def test_init_nao_sobrescreve_config_existente(tmp_path):
    home = tmp_path / "h"
    init_home(home)
    before = (home / "config.env").read_text(encoding="utf-8")
    result = init_home(home)
    assert (home / "config.env").read_text(encoding="utf-8") == before
    assert result["created"] == [] and sorted(result["kept"]) == sorted(KEYS)


def test_init_completa_so_o_que_falta(tmp_path):
    home = tmp_path / "h"
    home.mkdir()
    (home / "config.env").write_text("BRIDGE_SECRET=" + "a" * 64 + "\nOUTRA=x\n", encoding="utf-8")
    result = init_home(home)
    values = load_env_file(home / "config.env")
    assert values["BRIDGE_SECRET"] == "a" * 64 and values["OUTRA"] == "x"
    assert sorted(result["created"]) == ["BRIDGE_CONTROL_SECRET", "BRIDGE_PIN"]


@POSIX
def test_init_cria_arquivo_com_permissao_0600(tmp_path):
    init_home(tmp_path / "h")
    assert (os.stat(tmp_path / "h" / "config.env").st_mode & 0o777) == 0o600


def test_init_com_caminho_com_espacos_e_acentos(tmp_path):
    home = tmp_path / "João Silva" / "dados heycode"
    init_home(home)
    assert (home / "config.env").is_file()


def test_init_nao_vaza_segredos_no_retorno(tmp_path):
    result = init_home(tmp_path / "h")
    values = load_env_file(tmp_path / "h" / "config.env")
    text = repr(result)
    assert all(v not in text for v in values.values())


def _legacy(tmp_path, with_env=True, with_db=True):
    src = tmp_path / "clone"
    (src / "bridge").mkdir(parents=True)
    if with_db:
        (src / "bridge" / "bridge.db").write_bytes(b"SQLite format 3\x00dados")
    if with_env:
        (src / ".env").write_text("BRIDGE_SECRET=" + "b" * 64 + "\n", encoding="utf-8")
    return src


def test_import_legacy_copia_sem_apagar_origem(tmp_path):
    src = _legacy(tmp_path)
    result = import_legacy(src, tmp_path / "h")
    assert sorted(result["copied"]) == ["config.env", "heycode.db"]
    assert (tmp_path / "h" / "heycode.db").read_bytes() == (src / "bridge" / "bridge.db").read_bytes()
    assert (src / ".env").exists() and (src / "bridge" / "bridge.db").exists()


def test_import_legacy_nao_sobrescreve_destino(tmp_path):
    src = _legacy(tmp_path)
    home = tmp_path / "h"
    home.mkdir()
    (home / "heycode.db").write_bytes(b"novo")
    result = import_legacy(src, home)
    assert (home / "heycode.db").read_bytes() == b"novo"
    assert result["skipped"] == ["heycode.db"] and result["copied"] == ["config.env"]


def test_import_legacy_origem_sem_env_relata_missing(tmp_path):
    result = import_legacy(_legacy(tmp_path, with_env=False), tmp_path / "h")
    assert result["copied"] == ["heycode.db"] and result["missing"] == ["config.env"]


def test_import_legacy_aceita_db_na_raiz_do_clone(tmp_path):
    src = tmp_path / "clone"
    src.mkdir()
    (src / "bridge.db").write_bytes(b"x")
    assert import_legacy(src, tmp_path / "h")["copied"] == ["heycode.db"]


def test_import_legacy_preserva_segredos_na_init_seguinte(tmp_path):
    src = _legacy(tmp_path)
    home = tmp_path / "h"
    import_legacy(src, home)
    init_home(home)
    assert load_env_file(home / "config.env")["BRIDGE_SECRET"] == "b" * 64
