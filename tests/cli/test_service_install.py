import plistlib
import subprocess
from pathlib import Path

import pytest

from heycode.service import ServiceSpec, install, render, restart, uninstall

BARRA = chr(92)
HOME = Path("/dados/heycode")
USER = Path("/home/ana")
CMD = ["/usr/bin/heycode"]
CMD_ESPACO = [BARRA.join(["C:", "Users", "João Silva", "AppData", "heycode.exe"])]


def flat(spec):
    return [" ".join(step.cmd) for step in spec.install + spec.uninstall]


def test_render_windows_gera_comando_schtasks_com_aspas():
    spec = render("win32", CMD_ESPACO, HOME, USER)
    assert isinstance(spec, ServiceSpec) and spec.path is None
    create = spec.install[0].cmd
    assert create[:2] == ["schtasks", "/Create"] and "/F" in create
    assert create[create.index("/SC") + 1] == "ONLOGON"
    tr = create[create.index("/TR") + 1]
    assert tr.startswith('"') and "João Silva" in tr and tr.endswith(" serve")
    assert spec.uninstall[0].cmd[:2] == ["schtasks", "/Delete"]


def test_render_macos_gera_plist_valido():
    spec = render("darwin", CMD, HOME, USER, uid=501)
    data = plistlib.loads(spec.content.encode("utf-8"))
    assert data["Label"] == "dev.heycode.bridge" and data["RunAtLoad"] is True and data["KeepAlive"] is True
    assert data["ProgramArguments"] == [*CMD, "serve"]
    assert data["EnvironmentVariables"]["HEYCODE_HOME"] == str(HOME)
    assert spec.path == USER / "Library" / "LaunchAgents" / "dev.heycode.bridge.plist"
    assert any("bootstrap" in c and "gui/501" in c for c in flat(spec))


def test_render_linux_gera_unidade_systemd_user():
    spec = render("linux", CMD, HOME, USER)
    for section in ("[Unit]", "[Service]", "[Install]"):
        assert section in spec.content
    assert 'ExecStart="/usr/bin/heycode" serve' in spec.content
    assert "Restart=on-failure" in spec.content and f"HEYCODE_HOME={HOME}" in spec.content
    assert "WantedBy=default.target" in spec.content
    assert spec.path == USER / ".config" / "systemd" / "user" / "heycode.service"
    assert any("--user" in c and "enable" in c for c in flat(spec))


def test_linux_com_espacos_no_caminho_fica_entre_aspas():
    spec = render("linux", ["/home/João Silva/.local/bin/heycode"], HOME, USER)
    assert 'ExecStart="/home/João Silva/.local/bin/heycode" serve' in spec.content


@pytest.mark.parametrize("plat", ["win32", "darwin", "linux"])
def test_nunca_pede_administrador(plat):
    spec = render(plat, CMD, HOME, USER, uid=501)
    text = " ".join(flat(spec)) + spec.content
    for proibido in ("sudo", "SYSTEM", "HIGHEST", "/etc/systemd/system", "/Library/LaunchDaemons", "runas"):
        assert proibido not in text
    if spec.path:
        assert str(USER) in str(spec.path)


def test_plataforma_desconhecida_levanta_erro():
    with pytest.raises(ValueError):
        render("plan9", CMD, HOME, USER)


class Runner:
    def __init__(self, fail_on=None):
        self.calls = []
        self.fail_on = fail_on

    def __call__(self, cmd, **kwargs):
        self.calls.append(cmd)
        code = 1 if self.fail_on and self.fail_on in " ".join(cmd) else 0
        return subprocess.CompletedProcess(cmd, code, stdout="", stderr="falhou")


def kw(tmp_path, **extra):
    return {"home": HOME, "user_home": tmp_path, "command": CMD, **extra}


def test_dry_run_nao_executa_nada_nem_escreve(tmp_path):
    r = Runner()
    lines = install(platform="linux", apply=False, runner=r, **kw(tmp_path))
    assert r.calls == [] and not (tmp_path / ".config").exists()
    assert any("heycode.service" in ln for ln in lines) and any("dry-run" in ln.lower() for ln in lines)


def test_apply_escreve_o_arquivo_e_chama_o_executor(tmp_path):
    r = Runner()
    install(platform="linux", apply=True, runner=r, **kw(tmp_path))
    unit = tmp_path / ".config" / "systemd" / "user" / "heycode.service"
    assert "ExecStart" in unit.read_text(encoding="utf-8")
    assert any("enable" in " ".join(c) for c in r.calls)


def test_apply_duas_vezes_e_idempotente(tmp_path):
    r = Runner()
    for _ in range(2):
        install(platform="linux", apply=True, runner=r, **kw(tmp_path))
    unit = tmp_path / ".config" / "systemd" / "user" / "heycode.service"
    assert unit.read_text(encoding="utf-8").count("[Service]") == 1


def test_apply_macos_tolera_bootout_que_falha_na_primeira_vez(tmp_path):
    r = Runner(fail_on="bootout")
    install(platform="darwin", apply=True, runner=r, **kw(tmp_path, uid=501))
    assert any("bootstrap" in " ".join(c) for c in r.calls)


def test_apply_falha_em_passo_obrigatorio_levanta_erro(tmp_path):
    with pytest.raises(RuntimeError):
        install(platform="linux", apply=True, runner=Runner(fail_on="enable"), **kw(tmp_path))


def test_uninstall_remove_o_arquivo_e_e_idempotente(tmp_path):
    r = Runner()
    install(platform="linux", apply=True, runner=r, **kw(tmp_path))
    uninstall(platform="linux", apply=True, runner=r, **kw(tmp_path))
    assert not (tmp_path / ".config" / "systemd" / "user" / "heycode.service").exists()
    uninstall(platform="linux", apply=True, runner=r, **kw(tmp_path))


def test_uninstall_dry_run_mantem_o_arquivo(tmp_path):
    r = Runner()
    install(platform="linux", apply=True, runner=r, **kw(tmp_path))
    uninstall(platform="linux", apply=False, runner=r, **kw(tmp_path))
    assert (tmp_path / ".config" / "systemd" / "user" / "heycode.service").exists()


def test_restart_e_tolerante_a_falha():
    assert restart(platform="linux", runner=Runner(fail_on="restart"), uid=501) is False
    assert restart(platform="linux", runner=Runner(), uid=501) is True
    assert restart(platform="darwin", runner=Runner(), uid=501) is True
    assert restart(platform="win32", runner=Runner(), uid=501) is True
