"""Gate pre-commit: mudanca de arquitetura exige um novo ADR no staging."""

import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # hooks nao deixam __pycache__ no projeto
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lint import run_lint  # noqa: E402
from secret_scan import scan_staged  # noqa: E402

CONFIG_PATH = Path(__file__).with_name("gates.json")


def _is_new_adr(status: str, path: str, adr_dir: str) -> bool:
    prefix = adr_dir.strip("/") + "/"
    if status != "A" or not path.startswith(prefix):
        return False
    name = path[len(prefix) :]
    return re.fullmatch(r"\d{4}-.+\.md", name) is not None and not name.startswith("0000-")


def check_staged(staged: list[tuple[str, str]], config: dict) -> list[str]:
    patterns = config["architecture_paths"]
    touched = [p for _, p in staged if any(fnmatch.fnmatch(p, pat) for pat in patterns)]
    if not touched:
        return []
    if any(_is_new_adr(s, p, config["adr_dir"]) for s, p in staged):
        return []
    return [
        "Mudanca de arquitetura exige um NOVO ADR em "
        f"{config['adr_dir']}/NNNN-titulo.md (git add). Arquivos: " + ", ".join(touched)
    ]


def _matches(path: str, globs: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, g) for g in globs)


def _is_test(path: str, config: dict) -> bool:
    return _matches(path, config["test_globs"])


def _is_code(path: str, config: dict) -> bool:
    return (
        _matches(path, config["code_globs"])
        and not _is_test(path, config)
        and not _matches(path, config["ignored_code_globs"])
    )


def check_tests_with_code(files: list[str], commit_type: str, config: dict) -> list[str]:
    """G4: feat/fix que altera codigo de produto precisa alterar teste no mesmo commit."""
    if commit_type not in ("feat", "fix"):
        return []
    code = [f for f in files if _is_code(f, config)]
    if not code or any(_is_test(f, config) for f in files):
        return []
    return ["G4: " + commit_type + " altera codigo sem alterar teste no mesmo commit: " + ", ".join(code)]


def check_diff_size(added_by_file: dict[str, int], config: dict) -> list[str]:
    """G12: limite de linhas adicionadas, excluindo docs, travas e gerados."""
    counted = sum(n for f, n in added_by_file.items() if not _matches(f, config["size_exclude_globs"]))
    limit = config["max_added_lines"]
    if counted <= limit:
        return []
    return [f"G12: {counted} linhas adicionadas (limite {limit}, sem docs e travas). Divida em tarefas menores."]


def local_warnings(files: list[str], added_by_file: dict[str, int], config: dict) -> list[str]:
    """G4 e G12 so avisam no hook (o tipo do commit ainda nao existe); o CI bloqueia."""
    return check_tests_with_code(files, "feat", config) + check_diff_size(added_by_file, config)


def _read_added_lines() -> dict[str, int]:
    out = subprocess.run(
        ["git", "diff", "--cached", "--numstat", "-z"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    ).stdout
    added: dict[str, int] = {}
    for entry in out.split("\0"):
        parts = entry.split("\t")
        if len(parts) == 3 and parts[0].isdigit():
            added[parts[2]] = int(parts[0])
    return added


def _read_staged() -> list[tuple[str, str]]:
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-status", "-M", "-z"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    ).stdout
    return parse_name_status(out)


def parse_name_status(out: str) -> list[tuple[str, str]]:
    """Interpreta `git diff --name-status -M -z`; renomeacao vira (D, antigo) + (A, novo)."""
    parts = out.split("\0")
    staged: list[tuple[str, str]] = []
    i = 0
    while i < len(parts) and parts[i]:
        status = parts[i]
        if status[0] in "RC":
            old, new = parts[i + 1], parts[i + 2]
            if status[0] == "R":
                staged.append(("D", old))
            staged.append(("A", new))
            i += 3
        else:
            staged.append((status[0], parts[i + 1]))
            i += 2
    return staged


def main() -> int:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    staged = _read_staged()
    errors = check_staged(staged, config)
    errors += scan_staged()
    errors += run_lint([p for s, p in staged if s != "D"], format_files=[p for s, p in staged if s == "A"])
    for w in local_warnings([p for s, p in staged if s != "D"], _read_added_lines(), config):
        print(f"pre-commit (aviso, o CI bloqueia): {w}", file=sys.stderr)
    for e in errors:
        print(f"pre-commit: {e}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
