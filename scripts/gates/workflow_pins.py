"""Gate G8 (parte): toda acao de workflow precisa estar fixada por hash de commit, nao por tag movel."""

import re
import sys
from pathlib import Path

USES = re.compile(r"^\s*-?\s*uses:\s*(\S+)", re.MULTILINE)
PINNED = re.compile(r"@[0-9a-f]{40}$")


def check_workflow_pins(text: str) -> list[str]:
    errors = []
    for ref in USES.findall(text):
        ref = ref.strip("'\"")
        if ref.startswith("./"):
            continue
        if not PINNED.search(ref):
            errors.append(f"G8: acao sem hash de commit fixo: {ref}")
    return errors


if __name__ == "__main__":
    bad = []
    for wf in sorted(Path(".github/workflows").glob("*.yml")):
        bad += [f"{wf.name}: {e}" for e in check_workflow_pins(wf.read_text(encoding="utf-8"))]
    for e in bad:
        print(e, file=sys.stderr)
    sys.exit(1 if bad else 0)
