"""Gates do CI (autoridade): repetem G1-G4 em cada commit do PR; G11/G15 exigem aprovacao humana/revisor."""

import fnmatch
import json
import os
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


def _touched(changed: list[str], globs: list[str]) -> list[str]:
    return [p for p in changed if any(fnmatch.fnmatch(p, g) for g in globs)]


def check_protected(changed: list[str], approvers: set[str], author: str, config: dict) -> list[str]:
    """G11/G15: caminhos protegidos e sensiveis exigem aprovacao de um humano dono que nao seja o autor."""
    touched = _touched(changed, config["protected_paths"] + config["human_review_paths"])
    if not touched:
        return []
    owners = set(config.get("human_owners", []))
    if not owners:
        return ["G11: 'human_owners' vazio em gates.json; sem donos humanos nao ha como aprovar: " + ", ".join(touched)]
    if (approvers & owners) - {author}:
        return []
    return [
        "G11: caminhos protegidos/sensiveis exigem aprovacao de um dono humano diferente do autor: "
        + ", ".join(touched)
    ]


def check_agent_review(reviews: list[dict], head_sha: str, bot_login: str, author: str) -> list[str]:
    """G15: o ultimo parecer do revisor independente no commit atual precisa ser APPROVED."""
    if not bot_login:
        return ["G15: revisor independente nao configurado (AGENT_REVIEW_BOT vazio); falha fechada."]
    if bot_login == author:
        return ["G15: o revisor independente nao pode ser o autor do PR."]
    mine = [r for r in reviews if r["user"] == bot_login and r["commit"] == head_sha]
    if not mine:
        return [f"G15: sem revisao de {bot_login} no commit {head_sha[:7]}."]
    if mine[-1]["state"] != "APPROVED":
        return [f"G15: ultimo parecer de {bot_login} e {mine[-1]['state']}."]
    return []


def main(argv: list[str], repo: Path | None = None) -> int:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    mode = argv[1]
    repo = repo or Path(__file__).resolve().parents[2]
    if mode == "range":
        errors = check_range(argv[2], argv[3], config, repo)
    elif mode == "approvals":
        changed = changed_files(repo, argv[2], argv[3])
        approvers = {a for a in os.environ.get("PR_APPROVERS", "").split(",") if a}
        errors = check_protected(changed, approvers, os.environ.get("PR_AUTHOR", ""), config)
    elif mode == "agent-review":
        reviews = json.loads(Path(argv[3]).read_text(encoding="utf-8"))
        errors = check_agent_review(
            reviews, argv[2], os.environ.get("AGENT_REVIEW_BOT", ""), os.environ.get("PR_AUTHOR", "")
        )
    else:
        errors = [f"modo desconhecido: {mode}"]
    for e in errors:
        print(f"ci: {e}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
