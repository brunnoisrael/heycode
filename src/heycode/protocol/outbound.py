"""Montagem e envio de envelopes. Segredo e mascarado antes de assinar; o envio falha aberto (ADR 0029)."""

import os
import time
import uuid
from collections.abc import Callable
from typing import Any

from heycode.identity.signing import sign
from heycode.policy.redact import mask_secrets


def uuid7(now: float | None = None) -> str:
    ms = int((time.time() if now is None else now) * 1000) & ((1 << 48) - 1)
    rand = int.from_bytes(os.urandom(10), "big")
    value = (ms << 80) | (0x7 << 76) | ((rand >> 62) << 64) | (0x2 << 62) | (rand & ((1 << 62) - 1))
    return str(uuid.UUID(int=value))


def mask_payload(value: Any) -> Any:
    if isinstance(value, str):
        return mask_secrets(value)
    if isinstance(value, dict):
        return {k: mask_payload(v) for k, v in value.items()}
    if isinstance(value, list):
        return [mask_payload(v) for v in value]
    return value


def build_envelope(type_: str, payload: dict, *, installation_id: str, private_key, now: float) -> dict:
    envelope = {
        "v": 1,
        "id": uuid7(now),
        "ts": now,
        "installation_id": installation_id,
        "type": type_,
        "payload": mask_payload(payload),
    }
    envelope["sig"] = sign(envelope, private_key)
    return envelope


def send_fail_open(send: Callable[[dict], object], envelope: dict) -> bool:
    """Relay fora do ar nunca trava nem quebra o agente: devolve False e segue."""
    try:
        send(envelope)
    except Exception:  # noqa: BLE001 - falha aberta por desenho (AGENTS.md)
        return False
    return True
