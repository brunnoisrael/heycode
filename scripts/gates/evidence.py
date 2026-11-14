"""Gate G16: a mensagem da entrega traz comando e saida reais colados."""

import os
import re
import sys

SECTION = re.compile(r"^##\s*Evid[eê]ncia\s*$(.*?)(?=^##\s|\Z)", re.MULTILINE | re.DOTALL | re.IGNORECASE)
FENCE = re.compile(r"^`{3}[^\n]*\n(.*?)^`{3}\s*$", re.MULTILINE | re.DOTALL)


def check_evidence(body: str) -> list[str]:
    section = SECTION.search(body or "")
    if not section:
        return ["G16: a entrega nao tem a secao '## Evidencia'."]
    for block in FENCE.findall(section.group(1)):
        lines = [ln for ln in block.splitlines() if ln.strip()]
        if len(lines) >= 2:  # comando + pelo menos uma linha de saida
            return []
    return ["G16: preencha 'Evidencia' com um bloco de codigo com o comando e a saida real (2+ linhas)."]


if __name__ == "__main__":
    errors = check_evidence(os.environ.get("BODY", ""))
    for e in errors:
        print(f"ci: {e}", file=sys.stderr)
    sys.exit(1 if errors else 0)
