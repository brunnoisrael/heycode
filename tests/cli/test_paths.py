from pathlib import Path

from heycode.paths import config_file, db_path, home

BARRA = chr(92)
PERFIL = "C:" + BARRA + "Users" + BARRA + "Ana"
ROAMING = PERFIL + BARRA + "AppData" + BARRA + "Roaming"


def test_home_respeita_heycode_home():
    assert home({"HEYCODE_HOME": "/tmp/x"}, "linux") == Path("/tmp/x")


def test_home_windows_usa_appdata():
    env = {"APPDATA": ROAMING}
    assert home(env, "win32") == Path(ROAMING) / "heycode"


def test_home_windows_sem_appdata_cai_no_perfil():
    assert home({"USERPROFILE": PERFIL}, "win32") == Path(PERFIL) / "AppData" / "Roaming" / "heycode"


def test_home_macos():
    assert home({"HOME": "/Users/ana"}, "darwin") == Path("/Users/ana") / "Library" / "Application Support" / "heycode"


def test_home_linux_com_xdg():
    assert home({"XDG_DATA_HOME": "/dados", "HOME": "/home/ana"}, "linux") == Path("/dados") / "heycode"


def test_home_linux_padrao():
    assert home({"HOME": "/home/ana"}, "linux") == Path("/home/ana") / ".local" / "share" / "heycode"


def test_db_path_respeita_bridge_db():
    assert db_path({"BRIDGE_DB": "/x/y.db", "HEYCODE_HOME": "/h"}, "linux") == Path("/x/y.db")


def test_db_path_padrao_fica_no_home():
    assert db_path({"HEYCODE_HOME": "/h"}, "linux") == Path("/h") / "heycode.db"


def test_config_file_fica_no_home():
    assert config_file({"HEYCODE_HOME": "/h"}, "linux") == Path("/h") / "config.env"
