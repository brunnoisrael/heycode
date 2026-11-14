"""Compatibilidade para configurações antigas; falha aberta se a instalação estiver incompleta."""

import runpy
from pathlib import Path

try:
    runpy.run_path(str(Path(__file__).resolve().parent.parent / "src" / "heycode" / "hook.py"), run_name="__main__")
except BaseException:
    pass  # Um hook indisponível nunca deve bloquear o agente.
