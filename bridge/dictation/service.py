"""Ditado com confirmacao: guarda uma unica instrucao pendente e so envia apos confirmar."""
import threading
import time
from typing import Callable

try:  # no servidor, `bridge/` esta no sys.path; nos testes, o pacote e `bridge`
    from policy.redact import mask_secrets
except ImportError:  # pragma: no cover
    from bridge.policy.redact import mask_secrets

MAX_CHARS = 300
AGENTS = ("claude", "codex", "aider")

class Dictation:
    def __init__(self, start_run: Callable[[str, str, str | None], int], ttl: float = 60.0, clock=time.time,
                 check_project: Callable[[str | None], str | None] | None = None) -> None:
        self._start_run = start_run
        self._check_project = check_project  # fala de erro (projeto inexistente) ou None
        self._ttl = ttl
        self._clock = clock
        self._lock = threading.Lock()
        self._pending: dict | None = None
        self._expired = False
        self._peer = None  # outro tipo de pendencia (ProjectCreator): so uma vale por vez

    def link(self, peer) -> None:
        """Liga os dois lados da pendencia global unica (idempotente)."""
        if self._peer is peer:
            return
        self._peer = peer
        if hasattr(peer, "link"):
            peer.link(self)

    def discard(self) -> None:
        with self._lock:
            self._pending = None
            self._expired = False

    def has_pending(self) -> bool:
        with self._lock:
            if self._pending is not None and self._clock() - self._pending["t"] > self._ttl:
                self._pending = None  # expirada nunca vence
            return self._pending is not None

    def propose(self, agent: str, text: str, project: str | None = None) -> dict:
        agent = (agent or "").strip().lower()
        text = (text or "").strip()
        if self._peer is not None:
            self._peer.discard()  # fora do nosso lock: evita deadlock entre os dois lados
        with self._lock:
            self._pending = None
            self._expired = False
            if agent not in AGENTS:
                return {"speech": "Não conheço esse agente. Diga claude, codex ou aider.", "ok": False}
            if not text:
                return {"speech": "Não entendi a instrução. Pode repetir?", "ok": False}
            if len(text) > MAX_CHARS:
                return {"speech": f"A instrução passou de {MAX_CHARS} caracteres. Diga uma mais curta.", "ok": False}
            bad = self._check_project(project) if self._check_project else None
            if bad:
                return {"speech": bad, "ok": False}
            self._pending = {"agent": agent, "text": text, "project": project, "t": self._clock()}
        return {"speech": f"Entendi, para o {agent}: {mask_secrets(text)}. Confirma?", "ok": True}

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
            return {"speech": f"Não consegui iniciar o {p['agent']}: {mask_secrets(str(e))[:120]}"}
        return {"speech": f"Enviado ao {p['agent']}.", "run_id": run_id}

    def cancel(self) -> dict:
        with self._lock:
            had, self._pending = self._pending is not None, None
            self._expired = False
        return {"speech": "Ditado cancelado." if had else "Não há nada para cancelar."}
