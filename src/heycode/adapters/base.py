"""Contrato de adaptador de agente (ADR 0032): capacidades declaradas e falha aberta."""

import enum
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


class Capability(enum.Enum):
    START = "start"
    INSTRUCT_OPEN_SESSION = "instruct_open_session"
    CANCEL = "cancel"
    RESUME = "resume"
    READ_RESULT = "read_result"


class UnsupportedCapability(Exception):
    def __init__(self, agent: str, capability: Capability) -> None:
        super().__init__(f"{agent} nao suporta {capability.value}")
        self.agent = agent
        self.capability = capability


@runtime_checkable
class AgentAdapter(Protocol):
    name: str

    def capabilities(self) -> frozenset[Capability]: ...
    def start(self, project: str, prompt: str) -> int: ...
    def instruct(self, session: str, text: str) -> int: ...
    def cancel(self, run: int) -> bool: ...
    def resume(self, session: str) -> Any: ...
    def result(self, run: int) -> dict | None: ...


_METHOD_CAPABILITY = {
    "start": Capability.START,
    "instruct": Capability.INSTRUCT_OPEN_SESSION,
    "cancel": Capability.CANCEL,
    "resume": Capability.RESUME,
    "result": Capability.READ_RESULT,
}


@dataclass(frozen=True)
class CallResult:
    ok: bool
    value: Any = None
    error: str | None = None


def invoke(adapter: AgentAdapter, method: str, *args: Any) -> CallResult:
    """Chama uma operacao do adaptador. Operacao nao declarada levanta UnsupportedCapability
    (a voz avisa antes de prometer); qualquer outro erro vira CallResult(ok=False): o agente segue."""
    capability = _METHOD_CAPABILITY[method]
    if capability not in adapter.capabilities():
        raise UnsupportedCapability(adapter.name, capability)
    try:
        return CallResult(True, getattr(adapter, method)(*args))
    except Exception as exc:  # noqa: BLE001 - adaptadores falham abertos (AGENTS.md)
        return CallResult(False, error=f"{type(exc).__name__}: {exc}")
