"""G16: registra o resultado real dos gates e da matriz, sem entrada manual."""

import os
import sys
from pathlib import Path


def check_evidence(gates: str, tests: str) -> list[str]:
    errors = []
    if gates != "success":
        errors.append("G16: gates ausentes ou sem sucesso.")
    if tests != "success":
        errors.append("G16: matriz de testes ausente ou sem sucesso.")
    return errors


def main() -> int:
    gates = os.environ.get("GATES_RESULT", "")
    tests = os.environ.get("TESTS_RESULT", "")
    errors = check_evidence(gates, tests)
    for error in errors:
        print(f"ci: {error}", file=sys.stderr)
    if errors:
        return 1
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        sha = os.environ.get("GITHUB_SHA", "")
        with Path(summary).open("a", encoding="utf-8") as output:
            output.write(f"## Evidência de CI\n\nCommit: `{sha}`\n\nGates: {gates}. Matriz: {tests}.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
