"""Gate G5: detecta segredos em linhas adicionadas. Nunca imprime o valor encontrado."""

import re
import subprocess
import sys

ALLOW_MARKER = "gate:allow-secret"

# (nome, regex) para formatos conhecidos.
KNOWN = [
    ("chave AWS", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("token GitHub", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b")),
    ("token Slack", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("chave privada", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("bearer longo", re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{24,}")),
]
ASSIGN = re.compile(
    r"(?i)\b[A-Z0-9_]*(?:SECRET|TOKEN|PASSWORD|PASSWD|API_?KEY)[A-Z0-9_]*\s*[=:]\s*[\"']?([A-Za-z0-9/+_.\-]{24,})"
)
PLACEHOLDER = re.compile(r"(?i)^(x+|\*+|<.*>|.*(changeme|example|placeholder|seu-|your[-_]|dummy|secret-here).*)$")


ENV_READ = re.compile(r"^(process\.env|os\.environ|os\.getenv|getenv|env\.)", re.IGNORECASE)


def _is_placeholder(value: str) -> bool:
    return bool(PLACEHOLDER.match(value)) or len(set(value)) <= 4


def scan_text(path: str, text: str) -> list[str]:
    found: list[str] = []
    for n, line in enumerate(text.splitlines(), 1):
        if ALLOW_MARKER in line:
            continue
        for name, rx in KNOWN:
            if rx.search(line):
                found.append(f"G5: possivel {name} em {path}:{n}")
        m = ASSIGN.search(line)
        if m and not _is_placeholder(m.group(1)) and not ENV_READ.search(m.group(1)):
            found.append(f"G5: possivel segredo atribuido em {path}:{n}")
    return found


def scan_diff(diff: str) -> list[str]:
    """Varre apenas as linhas adicionadas de um `git diff`."""
    found: list[str] = []
    path = "?"
    for line in diff.splitlines():
        if line.startswith("+++ "):
            path = line[4:].removeprefix("b/")
        elif line.startswith("+") and not line.startswith("+++"):
            found += scan_text(path, line[1:])
    return found


def scan_staged() -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--cached", "-U0", "--no-color"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    ).stdout
    return scan_diff(out)


def scan_range(base: str, head: str, repo: str = ".") -> list[str]:
    """Varre cada commit do intervalo: um segredo adicionado e removido depois continua no historico."""
    out = subprocess.run(
        ["git", "-C", repo, "log", "-p", "-U0", "--no-color", f"{base}..{head}"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    ).stdout
    return scan_diff(out)


if __name__ == "__main__":
    errors = scan_range(sys.argv[1], sys.argv[2]) if len(sys.argv) == 3 else scan_staged()
    for e in errors:
        print(e, file=sys.stderr)
    sys.exit(1 if errors else 0)
