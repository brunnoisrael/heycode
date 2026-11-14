"""Gate G7: cobertura das linhas novas (piso global) e de ramos nas linhas tocadas de src/heycode/policy."""

import fnmatch
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from diffparse import parse_added_lines  # noqa: E402,F401  (reexportado)
from pre_commit import _is_code  # noqa: E402

POLICY_GLOB = "src/heycode/policy/*"


def check_coverage(added: dict[str, set[int]], cov: dict, config: dict) -> list[str]:
    errors: list[str] = []
    files = {k.replace(chr(92), "/"): v for k, v in cov.get("files", {}).items()}  # relatorio do Windows
    covered = total = 0
    for path, lines in added.items():
        report = files.get(path)
        if report is None:
            if _is_code(path, config) and path.endswith(".py"):
                errors.append(f"G7: {path} e codigo alterado mas nao aparece no relatorio de cobertura.")
            continue
        executed, missing = set(report["executed_lines"]), set(report["missing_lines"])
        covered += len(lines & executed)
        total += len(lines & (executed | missing))
        if fnmatch.fnmatch(path, POLICY_GLOB):
            bad = sorted({b[0] for b in report.get("missing_branches", []) if b[0] in lines})
            if bad:
                errors.append(f"G7: ramo sem cobertura em {path}, linhas {bad} (piso 100% de ramos na politica).")
    floor = config["diff_coverage_floor"]
    if total and covered * 100 < floor * total:
        errors.insert(0, f"G7: cobertura das linhas novas {covered * 100 // total}% (piso {floor}%).")
    return errors


def main(argv: list[str]) -> int:
    base, head, cov_path = argv[1:4]
    config = json.loads(Path(__file__).with_name("gates.json").read_text(encoding="utf-8"))
    diff = subprocess.run(
        ["git", "diff", "-U0", "--no-color", f"{base}..{head}"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    ).stdout
    cov = json.loads(Path(cov_path).read_text(encoding="utf-8"))
    errors = check_coverage(parse_added_lines(diff), cov, config)
    for e in errors:
        print(f"ci: {e}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
