"""Protocolo local<->relay (ADR 0029). Esquemas em `protocol/v1/`."""

import json
from pathlib import Path

import jsonschema

SUPPORTED_VERSIONS = frozenset({1})


class ProtocolError(Exception):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


def _schema_dir() -> Path:
    here = Path(__file__).resolve()
    for cand in (here.parents[1] / "_protocol" / "v1", here.parents[3] / "protocol" / "v1"):
        if cand.is_dir():
            return cand
    raise FileNotFoundError("esquemas do protocolo v1 nao encontrados")


def _load(name: str) -> dict:
    return json.loads((_schema_dir() / f"{name}.schema.json").read_text(encoding="utf-8"))


_validators: dict[str, jsonschema.Draft202012Validator] = {}


def _validator(name: str) -> jsonschema.Draft202012Validator:
    if name not in _validators:
        _validators[name] = jsonschema.Draft202012Validator(_load(name))
    return _validators[name]


def _check(name: str, data: object) -> None:
    errors = sorted(_validator(name).iter_errors(data), key=lambda e: list(e.path))
    if errors:
        raise ProtocolError("invalid", f"{name}: {errors[0].message}")


def validate(message: dict) -> None:
    """Levanta ProtocolError('unsupported_version'|'invalid'). Campos desconhecidos sao ignorados."""
    if not isinstance(message, dict):
        raise ProtocolError("invalid", "envelope deve ser objeto")
    v = message.get("v")
    if isinstance(v, int) and not isinstance(v, bool) and v not in SUPPORTED_VERSIONS and v > max(SUPPORTED_VERSIONS):
        raise ProtocolError("unsupported_version", f"versao {v} nao suportada")
    _check("envelope", message)
    _check(message["type"], message["payload"])
