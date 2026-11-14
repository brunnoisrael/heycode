"""Gates do CI: verificam os commits do intervalo."""

import json
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # hooks nao deixam __pycache__ no projeto
sys.path.insert(0, str(Path(__file__).resolve().parent))
from commit_msg import TYPE_RE, check_commit_message  # noqa: E402
from pre_commit import check_staged, check_tests_with_code, parse_name_status  # noqa: E402

CONFIG_PATH = Path(__file__).with_name("gates.json")


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8", check=True
    ).stdout


def changed_files(repo: Path, base: str, head: str) -> list[str]:
    """Todos os caminhos tocados, sem deteccao de renomeacao (mover arquivo protegido nao esconde o antigo)."""
    out = _git(Path(repo), "diff", "--name-only", "--no-renames", "-z", f"{base}..{head}")
    return [p for p in out.split("\0") if p]


def check_range(base: str, head: str, config: dict, repo_root: Path) -> list[str]:
    """Aplica G1, G2, G3, G4 a cada commit entre base e head (merges ignorados)."""
    repo = Path(repo_root)
    errors: list[str] = []
    for sha in _git(repo, "rev-list", "--no-merges", "--reverse", f"{base}..{head}").split():
        message = _git(repo, "log", "-1", "--format=%B", sha)
        tag = sha[:7]
        errors += [f"{tag}: {e}" for e in check_commit_message(message, repo, config)]
        files = parse_name_status(_git(repo, "diff-tree", "--no-commit-id", "--name-status", "-r", "-M", "-z", sha))
        errors += [f"{tag}: {e}" for e in check_staged(files, config)]
        subject = next((ln.strip() for ln in message.splitlines() if ln.strip()), "")
        m = TYPE_RE.match(subject)
        if m:
            paths = [p for s, p in files if s != "D"]
            errors += [f"{tag}: {e}" for e in check_tests_with_code(paths, m.group(1), config)]
    return errors


def main(argv: list[str], repo: Path | None = None) -> int:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    mode = argv[1]
    repo = repo or Path(__file__).resolve().parents[2]
    if mode == "range":
        errors = check_range(argv[2], argv[3], config, repo)
    else:
        errors = [f"modo desconhecido: {mode}"]
    for e in errors:
        print(f"ci: {e}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
