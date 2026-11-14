"""Onde o HeyCode guarda configuracao e estado do usuario (ADR 0027)."""

import os
import sys
from collections.abc import Mapping
from pathlib import Path


def _user_home(env: Mapping[str, str]) -> Path:
    return Path(env.get("HOME") or env.get("USERPROFILE") or Path.home())


def home(env: Mapping[str, str] | None = None, platform: str | None = None) -> Path:
    """Diretorio do usuario: HEYCODE_HOME, ou o padrao do sistema."""
    env = os.environ if env is None else env
    platform = platform or sys.platform
    if env.get("HEYCODE_HOME"):
        return Path(env["HEYCODE_HOME"]).expanduser()
    user = _user_home(env)
    if platform == "win32":
        return Path(env.get("APPDATA") or user / "AppData" / "Roaming") / "heycode"
    if platform == "darwin":
        return user / "Library" / "Application Support" / "heycode"
    return Path(env.get("XDG_DATA_HOME") or user / ".local" / "share") / "heycode"


def db_path(env: Mapping[str, str] | None = None, platform: str | None = None) -> Path:
    env = os.environ if env is None else env
    if env.get("BRIDGE_DB"):
        return Path(env["BRIDGE_DB"])
    return home(env, platform) / "heycode.db"


def config_file(env: Mapping[str, str] | None = None, platform: str | None = None) -> Path:
    return home(env, platform) / "config.env"
