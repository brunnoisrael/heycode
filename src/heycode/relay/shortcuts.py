"""Atalhos para agentes (ADR 0048, fase A): normalizacao e casamento do que a pessoa falou.

O casamento erra para o lado seguro: empate ou semelhanca baixa viram recusa, e mesmo um acerto so dispara um
ditado que pede "Confirma?" por voz antes de qualquer execucao.
"""

import re
import unicodedata
from difflib import SequenceMatcher

LEADING = {"o", "a", "os", "as", "um", "uma", "comando", "atalho"}
FUZZY_MIN = 0.85
TIE_MARGIN = 0.03


def normalize(text: object) -> str:
    """Minusculas, sem acento nem pontuacao, espacos colapsados e sem artigo/"comando" no comeco."""
    decomposed = unicodedata.normalize("NFD", str(text or ""))
    plain = "".join(c for c in decomposed if not unicodedata.combining(c)).lower()
    words = re.sub(r"[^a-z0-9]+", " ", plain).split()
    while words and words[0] in LEADING:
        words.pop(0)
    return " ".join(words)


def _names(shortcut: dict) -> list[str]:
    return [n for n in (normalize(shortcut["name"]), *(normalize(a) for a in shortcut.get("aliases", []))) if n]


def match(spoken: str, shortcuts: list[dict]) -> tuple[dict | None, str]:
    """(atalho, "ok") | (None, "none") | (None, "ambiguous"). So atalhos ligados entram."""
    said = normalize(spoken)
    live = [s for s in shortcuts if s.get("enabled", True)]
    if len(said) < 2 or not live:
        return None, "none"
    exact = [s for s in live if said in _names(s)]
    if len(exact) == 1:
        return exact[0], "ok"
    if len(exact) > 1:
        return None, "ambiguous"
    scored = sorted(
        ((max(SequenceMatcher(None, said, n).ratio() for n in _names(s)), s) for s in live if _names(s)),
        key=lambda pair: pair[0],
        reverse=True,
    )
    if not scored or scored[0][0] < FUZZY_MIN:
        return None, "none"
    if len(scored) > 1 and scored[1][0] >= FUZZY_MIN and scored[0][0] - scored[1][0] < TIE_MARGIN:
        return None, "ambiguous"
    return scored[0][1], "ok"
