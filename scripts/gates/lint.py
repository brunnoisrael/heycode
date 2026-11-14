"""Gate G6: ruff (lint e formato) nos arquivos Python alterados. Falha fechada se a ferramenta faltar.

`ruff check` so acusa linhas alteradas (o legado so e corrigido quando e tocado) e `ruff format --check`
so vale para arquivos realmente novos. Sem `added_lines`, o check vale para o arquivo inteiro.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from diffparse import parse_added_lines  # noqa: E402

# A configuracao viaja com os gates (o scaffold de projeto novo copia scripts/gates inteiro).
CONFIG = str(Path(__file__).with_name("ruff.toml"))


def _rel(filename: str) -> str:
    return os.path.relpath(filename).replace(chr(92), "/")


def _check_changed_lines(runner, py: list[str], added_lines: dict[str, set[int]]) -> list[str]:
    cmd = [sys.executable, "-m", "ruff", "check", "--output-format", "json", "--config", CONFIG, *py]
    try:
        result = runner(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        diagnostics = json.loads(result.stdout or "[]")
    except FileNotFoundError:
        return ["G6: ruff nao encontrado; instale com `pip install -r requirements-dev.txt`."]
    except json.JSONDecodeError:
        return ["G6: saida ilegivel do ruff check: " + (result.stderr or result.stdout or "").strip()[:200]]
    errors = []
    for d in diagnostics:
        path, row = _rel(d["filename"]), d["location"]["row"]
        if row in added_lines.get(path, set()):
            errors.append(f"G6: {path}:{row} {d['code']} {d['message']}")
    return errors


def run_lint(
    files: list[str],
    runner=subprocess.run,
    format_files: list[str] | None = None,
    added_lines: dict[str, set[int]] | None = None,
) -> list[str]:
    py = [f for f in files if f.endswith(".py")]
    if not py:
        return []
    fmt = py if format_files is None else [f for f in format_files if f.endswith(".py")]
    errors: list[str] = []
    if added_lines is not None:
        errors += _check_changed_lines(runner, py, added_lines)
        commands = []
    else:
        commands = [[sys.executable, "-m", "ruff", "check", "--config", CONFIG, *py]]
    if fmt:
        commands.append([sys.executable, "-m", "ruff", "format", "--check", "--config", CONFIG, *fmt])
    for cmd in commands:
        try:
            result = runner(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        except FileNotFoundError:
            return ["G6: ruff nao encontrado; instale com `pip install -r requirements-dev.txt`."]
        if result.returncode != 0:
            tail = (result.stdout or result.stderr or "").strip().splitlines()[-5:]
            errors.append("G6: " + " ".join(cmd[3:5]) + " falhou:\n" + "\n".join(tail))
    return errors


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, encoding="utf-8", errors="replace", check=True
    ).stdout


def main(argv: list[str]) -> int:
    """CI: `lint.py BASE HEAD` valida as linhas alteradas e os arquivos novos do intervalo."""
    base, head = argv[1], argv[2]
    changed = [p for p in _git("diff", "--name-only", "-z", "--diff-filter=ACMR", f"{base}..{head}").split(chr(0)) if p]
    new = [p for p in _git("diff", "--name-only", "-z", "--diff-filter=A", f"{base}..{head}").split(chr(0)) if p]
    added = parse_added_lines(_git("diff", "-U0", "--no-color", f"{base}..{head}"))
    errors = run_lint(changed, format_files=new, added_lines=added)
    for e in errors:
        print(f"ci: {e}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
