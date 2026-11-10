"""Ditado com confirmacao: guarda uma unica instrucao pendente e so envia apos confirmar."""
import re
import threading
import time
from typing import Callable

MAX_CHARS = 300
AGENTS = ("claude", "codex", "aider")

# TODO(ligacao): trocar por policy.redact.mask_secrets (Task H) quando o servidor for ligado.
_SECRET_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_\-]{10,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"(?i)\b(password|passwd|senha|secret|token|api[_-]?key)\s*[=:]\s*\S+"),
]


def _mask(text: str) -> str:
    for pat in _SECRET_PATTERNS:
        text = pat.sub("[segredo]", text)
    return text


class Dictation:
    def __init__(self, start_run: Callable[[str, str, str | None], int], ttl: float = 60.0, clock=time.time) -> None:
        self._start_run = start_run
        self._ttl = ttl
        self._clock = clock
        self._lock = threading.Lock()
        self._pending: dict | None = None
        self._expired = False

    def propose(self, agent: str, text: str, project: str | None = None) -> dict:
        agent = (agent or "").strip().lower()
        text = (text or "").strip()
        with self._lock:
            self._pending = None
            self._expired = False
            if agent not in AGENTS:
                return {"speech": "Não conheço esse agente. Diga claude, codex ou aider.", "ok": False}
            if not text:
                return {"speech": "Não entendi a instrução. Pode repetir?", "ok": False}
            if len(text) > MAX_CHARS:
                return {"speech": f"A instrução passou de {MAX_CHARS} caracteres. Diga uma mais curta.", "ok": False}
            self._pending = {"agent": agent, "text": text, "project": project, "t": self._clock()}
        return {"speech": f"Entendi, para o {agent}: {_mask(text)}. Confirma?", "ok": True}

    def confirm(self) -> dict:
        with self._lock:
            p, self._pending = self._pending, None
            expired, self._expired = self._expired, False
            if p is None:
                if expired:
                    return {"speech": "O ditado expirou. Nada foi enviado."}
                return {"speech": "Não há nada para confirmar."}
            if self._clock() - p["t"] > self._ttl:
                return {"speech": "O ditado expirou. Nada foi enviado."}
        try:
            run_id = self._start_run(p["agent"], p["text"], p["project"])
        except Exception as e:  # nunca derruba a ponte; a mensagem sai mascarada
            return {"speech": f"Não consegui iniciar o {p['agent']}: {_mask(str(e))[:120]}"}
        return {"speech": f"Enviado ao {p['agent']}.", "run_id": run_id}

    def cancel(self) -> dict:
        with self._lock:
            had, self._pending = self._pending is not None, None
            self._expired = False
        return {"speech": "Ditado cancelado." if had else "Não há nada para cancelar."}
