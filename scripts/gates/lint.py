"""Gate G6: ruff (lint e formato) nos arquivos Python alterados. Falha fechada se a ferramenta faltar."""

import subprocess
import sys


def run_lint(files: list[str], runner=subprocess.run) -> list[str]:
    py = [f for f in files if f.endswith(".py")]
    if not py:
        return []
    commands = [
        [sys.executable, "-m", "ruff", "check", *py],
        [sys.executable, "-m", "ruff", "format", "--check", *py],
    ]
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
