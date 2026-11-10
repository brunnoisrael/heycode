"""Gate pre-commit: mudanca de arquitetura exige um novo ADR no staging."""
import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path

CONFIG_PATH = Path(__file__).with_name("gates.json")


def _is_new_adr(status: str, path: str, adr_dir: str) -> bool:
    prefix = adr_dir.strip("/") + "/"
    if status != "A" or not path.startswith(prefix):
        return False
    name = path[len(prefix):]
    return re.fullmatch(r"\d{4}-.+\.md", name) is not None and not name.startswith("0000-")


def check_staged(staged: list[tuple[str, str]], config: dict) -> list[str]:
    patterns = config["architecture_paths"]
    touched = [
        p for _, p in staged if any(fnmatch.fnmatch(p, pat) for pat in patterns)
    ]
    if not touched:
        return []
    if any(_is_new_adr(s, p, config["adr_dir"]) for s, p in staged):
        return []
    return [
        "Mudanca de arquitetura exige um NOVO ADR em "
        f"{config['adr_dir']}/NNNN-titulo.md (git add). Arquivos: " + ", ".join(touched)
    ]


def _read_staged() -> list[tuple[str, str]]:
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-status", "-M", "-z"],
        capture_output=True, text=True, encoding="utf-8", check=True,
    ).stdout
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
    errors = check_staged(_read_staged(), config)
    for e in errors:
        print(f"pre-commit: {e}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
