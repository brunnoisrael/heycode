"""Mascara segredos em texto que vai para voz, log ou resumo (spec §10)."""
import re

MASK = "[segredo]"
_NB = r"(?<![A-Za-z0-9])"  # \b falha depois de "_"; este limite nao.

_PATTERNS = [
    re.compile(_NB + r"sk-[A-Za-z0-9_\-]{16,}"),
    re.compile(_NB + r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(_NB + r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(_NB + r"(?:AKIA|ASIA)[A-Z0-9]{16}(?![A-Za-z0-9])"),
    re.compile(_NB + r"xox[bp]-[A-Za-z0-9\-]{8,}"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=\-]+"),
    re.compile(r"(?<=://)[^/\s:@]+:[^@\s]+(?=@)"),
    re.compile(r"(?i)" + _NB + r"[A-Za-z0-9_\-]*(?:key|token|secret|password|passwd|senha|pass|pwd)[ \t]*[=:][ \t]*\S+"),
    re.compile(r"(?<![A-Za-z0-9\-])-p\S+"),
]


def mask_secrets(text: str) -> str:
    for pat in _PATTERNS:
        text = pat.sub(MASK, text)
    return text
