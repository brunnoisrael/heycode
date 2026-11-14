"""Adaptadores dos agentes ja suportados, sobre o Supervisor e a fila de instrucoes (ADR 0007, 0018).

As capacidades declaradas refletem o que existe hoje: nenhum agente tem retomada (`RESUME`); so o Claude
recebe instrucao em sessao aberta sem cooperacao (hook Stop); o Codex so a receberia se chamasse a
ferramenta MCP por conta propria, entao nao declara a capacidade.
"""

from heycode.adapters.base import Capability, UnsupportedCapability

_MODE = "manual"


class SupervisorAdapter:
    name = ""
    _caps: frozenset[Capability] = frozenset()

    def __init__(self, supervisor, store, mode: str = _MODE) -> None:
        self._sup = supervisor
        self._store = store
        self._mode = mode

    def capabilities(self) -> frozenset[Capability]:
        return self._caps

    def start(self, project: str, prompt: str) -> int:
        return self._sup.start(self.name, prompt, project, self._mode)

    def instruct(self, session: str, text: str) -> int:
        if Capability.INSTRUCT_OPEN_SESSION not in self._caps:
            raise UnsupportedCapability(self.name, Capability.INSTRUCT_OPEN_SESSION)
        return self._store.add_instruction(text, agent=self.name, project=session)

    def cancel(self, run: int) -> bool:
        return self._sup.cancel(run)

    def resume(self, session: str):
        raise UnsupportedCapability(self.name, Capability.RESUME)

    def result(self, run: int) -> dict | None:
        return self._sup.status(run)


_BASE = frozenset({Capability.START, Capability.CANCEL, Capability.READ_RESULT})


class ClaudeAdapter(SupervisorAdapter):
    name = "claude"
    _caps = _BASE | {Capability.INSTRUCT_OPEN_SESSION}


class CodexAdapter(SupervisorAdapter):
    name = "codex"
    _caps = _BASE


class AiderAdapter(SupervisorAdapter):
    name = "aider"
    _caps = _BASE
