"""Gate commit-msg: exige trailer `Spec:` para tipos nao isentos."""

import json
import posixpath
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # hooks nao deixam __pycache__ no projeto
sys.path.insert(0, str(Path(__file__).resolve().parent))
from spec_status import DEFAULT_PATTERN, check_spec_approved  # noqa: E402

CONFIG_PATH = Path(__file__).with_name("gates.json")
TYPE_RE = re.compile(r"^([A-Za-z]+)(\([^)]*\))?!?:")
SPEC_RE = re.compile(r"^Spec:[ \t]*(.+?)[ \t]*$", re.IGNORECASE)


def _clean_lines(message: str) -> list[str]:
    lines = message.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return [ln for ln in lines if not ln.startswith("#")]


def check_commit_message(message: str, repo_root: Path, config: dict) -> list[str]:
    lines = _clean_lines(message)
    subject = next((ln.strip() for ln in lines if ln.strip()), "")
    if subject.startswith(("Merge ", "Revert ")):
        return []
    valid = config.get("valid_types", ["feat", "fix", "docs", "chore", "test", "refactor"])
    m = TYPE_RE.match(subject)
    if not m or m.group(1) not in valid:
        return ["Mensagem deve comecar com 'tipo: descricao'; tipos validos: " + "|".join(valid)]
    if m.group(1) in config["exempt_types"]:
        return []
    spec = None
    for ln in lines:
        sm = SPEC_RE.match(ln.strip())
        if sm:
            spec = sm.group(1)
    if spec is None:
        return ["Falta o trailer 'Spec: <arquivo>' (obrigatorio para feat/fix/test/refactor)."]
    path = posixpath.normpath(spec.replace("\\", "/"))
    spec_dir = config["spec_dir"].strip("/")
    if not path.startswith(spec_dir + "/"):
        return [f"Spec deve estar em {spec_dir}/: {spec}"]
    spec_file = Path(repo_root) / path
    if not spec_file.is_file():
        return [f"Spec inexistente: {spec}"]
    return check_spec_approved(spec_file, config.get("approved_status_regex", DEFAULT_PATTERN))


def main(argv: list[str]) -> int:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    message = Path(argv[1]).read_text(encoding="utf-8", errors="replace")
    errors = check_commit_message(message, Path(__file__).resolve().parents[2], config)
    for e in errors:
        print(f"commit-msg: {e}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
