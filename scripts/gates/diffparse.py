"""Interpreta `git diff -U0`: linhas adicionadas por arquivo."""

import re

HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def parse_added_lines(diff: str) -> dict[str, set[int]]:
    """Linhas adicionadas por arquivo, a partir de `git diff -U0`."""
    added: dict[str, set[int]] = {}
    path, line = "", 0
    for raw in diff.splitlines():
        if raw.startswith("+++ "):
            path = raw[4:].removeprefix("b/")
        elif m := HUNK.match(raw):
            line = int(m.group(1))
        elif raw.startswith("+") and not raw.startswith("+++"):
            added.setdefault(path, set()).add(line)
            line += 1
    return added
