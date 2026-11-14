"""Gate G2: a spec citada no trailer `Spec:` precisa estar aprovada."""

import re
from pathlib import Path

DEFAULT_PATTERN = r"^.*Status:\s*aprovad[ao]\b"
HEADER_LINES = 10


def check_spec_approved(spec_path: Path, pattern: str = DEFAULT_PATTERN) -> list[str]:
    """Retorna erros (lista vazia se aprovada). Procura `Status: aprovada` nas 10 primeiras linhas."""
    spec_path = Path(spec_path)
    try:
        text = spec_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return [f"Spec ilegivel ou inexistente: {spec_path.name}"]
    regex = re.compile(pattern, re.IGNORECASE)
    for line in text.splitlines()[:HEADER_LINES]:
        if regex.match(line):
            return []
    return [
        f"Spec sem 'Status: aprovada' nas {HEADER_LINES} primeiras linhas: {spec_path.name}. "
        "A aprovacao e do dono; agentes nao aprovam specs."
    ]
