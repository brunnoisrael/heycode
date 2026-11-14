"""Servico em segundo plano no nivel do usuario: Tarefa Agendada, LaunchAgent e systemd --user (ADR 0026).

Nunca pede administrador/root. `install`/`uninstall` fazem dry-run por padrao; `apply=True` age e e idempotente.
"""

import os
import plistlib
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

TASK_NAME = "HeyCodeBridge"
LABEL = "dev.heycode.bridge"
UNIT = "heycode.service"


@dataclass
class Step:
    cmd: list[str]
    tolerant: bool = False  # falha tolerada (ex.: remover o que ainda nao existe)


@dataclass
class ServiceSpec:
    path: Path | None
    content: str
    install: list[Step] = field(default_factory=list)
    uninstall: list[Step] = field(default_factory=list)


def default_command() -> list[str]:
    exe = shutil.which("heycode")
    return [exe] if exe else [sys.executable, "-m", "heycode.cli"]


def _platform(platform: str | None) -> str:
    name = platform or sys.platform
    return "linux" if name.startswith("linux") else name


def _default_uid() -> int:
    return os.getuid() if hasattr(os, "getuid") else 501


def _quote_windows(command: list[str]) -> str:
    parts = [f'"{t}"' if (i == 0 or " " in t) else t for i, t in enumerate([*command, "serve"])]
    return " ".join(parts)


def render(platform: str, command: list[str], home: Path, user_home: Path, uid: int | None = None) -> ServiceSpec:
    platform = _platform(platform)
    uid = _default_uid() if uid is None else uid
    if platform == "win32":
        create = ["schtasks", "/Create", "/TN", TASK_NAME, "/TR", _quote_windows(command)]
        create += ["/SC", "ONLOGON", "/RL", "LIMITED", "/F"]
        return ServiceSpec(
            path=None,
            content=" ".join(create),
            install=[Step(create), Step(["schtasks", "/Run", "/TN", TASK_NAME], tolerant=True)],
            uninstall=[Step(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"], tolerant=True)],
        )
    if platform == "darwin":
        path = user_home / "Library" / "LaunchAgents" / f"{LABEL}.plist"
        data = {
            "Label": LABEL,
            "ProgramArguments": [*command, "serve"],
            "RunAtLoad": True,
            "KeepAlive": True,
            "EnvironmentVariables": {"HEYCODE_HOME": str(home)},
            "StandardOutPath": str(home / "bridge.log"),
            "StandardErrorPath": str(home / "bridge.log"),
        }
        domain = f"gui/{uid}"
        return ServiceSpec(
            path=path,
            content=plistlib.dumps(data).decode("utf-8"),
            install=[
                Step(["launchctl", "bootout", domain, str(path)], tolerant=True),
                Step(["launchctl", "bootstrap", domain, str(path)]),
            ],
            uninstall=[Step(["launchctl", "bootout", domain, str(path)], tolerant=True)],
        )
    if platform == "linux":
        path = user_home / ".config" / "systemd" / "user" / UNIT
        exec_start = " ".join([f'"{command[0]}"', *command[1:], "serve"])
        content = (
            "[Unit]\nDescription=HeyCode bridge\nAfter=network.target\n\n"
            f"[Service]\nExecStart={exec_start}\nRestart=on-failure\nEnvironment=HEYCODE_HOME={home}\n\n"
            "[Install]\nWantedBy=default.target\n"
        )
        return ServiceSpec(
            path=path,
            content=content,
            install=[
                Step(["systemctl", "--user", "daemon-reload"]),
                Step(["systemctl", "--user", "enable", "--now", UNIT]),
            ],
            uninstall=[
                Step(["systemctl", "--user", "disable", "--now", UNIT], tolerant=True),
                Step(["systemctl", "--user", "daemon-reload"], tolerant=True),
            ],
        )
    raise ValueError(f"plataforma sem suporte a servico: {platform}")


def _run(steps: list[Step], runner) -> list[str]:
    done = []
    for step in steps:
        result = runner(step.cmd, capture_output=True, text=True)
        if result.returncode != 0 and not step.tolerant:
            raise RuntimeError(f"falhou: {' '.join(step.cmd)}: {(result.stderr or '').strip()}")
        done.append("executado: " + " ".join(step.cmd))
    return done


def _spec(platform, home, user_home, command, uid) -> ServiceSpec:
    from heycode import paths

    return render(
        _platform(platform),
        command or default_command(),
        Path(home) if home else paths.home(),
        Path(user_home) if user_home else Path.home(),
        uid,
    )


def _describe(spec: ServiceSpec, steps: list[Step], verb: str) -> list[str]:
    lines = [f"[dry-run] {verb}: nada foi alterado. Use --apply para executar."]
    if spec.path:
        lines.append(f"arquivo: {spec.path}")
        lines.extend("  " + ln for ln in spec.content.splitlines())
    lines.extend("comando: " + " ".join(s.cmd) for s in steps)
    return lines


def install(*, platform=None, apply=False, runner=subprocess.run, home=None, user_home=None, command=None, uid=None):
    spec = _spec(platform, home, user_home, command, uid)
    if not apply:
        return _describe(spec, spec.install, "instalação do serviço")
    lines = []
    if spec.path:
        spec.path.parent.mkdir(parents=True, exist_ok=True)
        spec.path.write_text(spec.content, encoding="utf-8", newline="\n")
        lines.append(f"escrito: {spec.path}")
    return lines + _run(spec.install, runner)


def uninstall(*, platform=None, apply=False, runner=subprocess.run, home=None, user_home=None, command=None, uid=None):
    spec = _spec(platform, home, user_home, command, uid)
    if not apply:
        return _describe(spec, spec.uninstall, "remoção do serviço")
    lines = _run(spec.uninstall, runner)
    if spec.path:
        spec.path.unlink(missing_ok=True)
        lines.append(f"removido: {spec.path}")
    return lines


def restart(*, platform=None, runner=subprocess.run, uid=None) -> bool:
    """Reinicia o servico se existir. Tolerante: devolve False em vez de levantar erro."""
    platform = _platform(platform)
    uid = _default_uid() if uid is None else uid
    if platform == "win32":
        cmds = [["schtasks", "/End", "/TN", TASK_NAME], ["schtasks", "/Run", "/TN", TASK_NAME]]
    elif platform == "darwin":
        cmds = [["launchctl", "kickstart", "-k", f"gui/{uid}/{LABEL}"]]
    else:
        cmds = [["systemctl", "--user", "restart", UNIT]]
    code = 1
    try:
        for cmd in cmds:
            code = runner(cmd, capture_output=True, text=True).returncode
    except OSError:
        return False
    return code == 0
