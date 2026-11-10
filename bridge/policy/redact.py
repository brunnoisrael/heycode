"""Mascara segredos em texto que vai para voz, log ou resumo (spec §10)."""
import re

MASK = "[segredo]"

_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    re.compile(r"(?i)\b(?:password|passwd|senha|secret|token|api[_-]?key)\s*[=:]\s*\S+"),
]


def mask_secrets(text: str) -> str:
    for pat in _PATTERNS:
        text = pat.sub(MASK, text)
    return text
