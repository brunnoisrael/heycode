"""Gate G6: ruff (lint e formato) nos arquivos Python alterados. Falha fechada se a ferramenta faltar."""

import subprocess
import sys
from pathlib import Path

# A configuracao viaja com os gates (o scaffold de projeto novo copia scripts/gates inteiro).
CONFIG = str(Path(__file__).with_name("ruff.toml"))


def run_lint(files: list[str], runner=subprocess.run, format_files: list[str] | None = None) -> list[str]:
    """`ruff check` em todo arquivo alterado; `ruff format --check` so nos novos (format_files).

    Arquivos legados editados nao precisam ser reformatados por inteiro (isso estouraria o G12).
    """
    py = [f for f in files if f.endswith(".py")]
    if not py:
        return []
    fmt = py if format_files is None else [f for f in format_files if f.endswith(".py")]
    commands = [[sys.executable, "-m", "ruff", "check", "--config", CONFIG, *py]]
    if fmt:
        commands.append([sys.executable, "-m", "ruff", "format", "--check", "--config", CONFIG, *fmt])
    errors: list[str] = []
    for cmd in commands:
        try:
            result = runner(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        except FileNotFoundError:
            return ["G6: ruff nao encontrado; instale com `pip install -r requirements-dev.txt`."]
        if result.returncode != 0:
            tail = (result.stdout or result.stderr or "").strip().splitlines()[-5:]
            errors.append("G6: " + " ".join(cmd[3:5]) + " falhou:\n" + "\n".join(tail))
    return errors
