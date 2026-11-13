"""Assinatura Ed25519 sobre JSON canonico (ADR 0030)."""

import base64
import binascii
import json

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from heycode.identity import IdentityError
from heycode.identity.keys import public_b64
from heycode.identity.registry import Registry
from heycode.identity.replay import ReplayWindow

DEFAULT_SKEW = 120


def canonical(data: dict) -> bytes:
    """JSON canonico: chaves ordenadas, sem espacos, UTF-8."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _body(envelope: dict) -> bytes:
    return canonical({k: v for k, v in envelope.items() if k != "sig"})


def sign(envelope: dict, private: Ed25519PrivateKey) -> str:
    return base64.b64encode(private.sign(_body(envelope))).decode("ascii")


def _check_sig(body: bytes, sig: object, public_key: str) -> None:
    if not isinstance(sig, str) or not sig:
        raise IdentityError("bad_signature", "assinatura ausente")
    try:
        Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key, validate=True)).verify(
            base64.b64decode(sig, validate=True), body
        )
    except (InvalidSignature, ValueError, binascii.Error) as exc:
        raise IdentityError("bad_signature", "assinatura invalida") from exc


def verify(
    envelope: dict,
    public_key: str,
    now: float,
    *,
    replay: ReplayWindow | None = None,
    registry: Registry | None = None,
) -> None:
    """Levanta IdentityError(revoked|bad_signature|clock_skew|replay). A ordem importa:
    revogacao e assinatura antes de gastar um id na janela de replay."""
    if registry is not None and registry.is_revoked(str(envelope.get("installation_id"))):
        raise IdentityError("revoked", "instalacao revogada")
    _check_sig(_body(envelope), envelope.get("sig"), public_key)
    ts = envelope.get("ts")
    if not isinstance(ts, (int, float)):
        raise IdentityError("bad_signature", "ts invalido")
    if replay is not None:
        replay.check(str(envelope.get("id")), float(ts), now)
    elif abs(now - ts) > DEFAULT_SKEW:
        raise IdentityError("clock_skew", "ts fora da janela de tolerancia")


def rotate(old_private: Ed25519PrivateKey, installation_id: str, new_public_key: str, ts: float) -> dict:
    """Declaracao de rotacao: a nova chave publica, assinada pela chave antiga."""
    stmt = {"installation_id": installation_id, "new_public_key": new_public_key, "ts": ts}
    stmt["sig"] = base64.b64encode(old_private.sign(_body(stmt))).decode("ascii")
    return stmt


def verify_rotation(statement: dict, old_public_key: str) -> None:
    _check_sig(_body(statement), statement.get("sig"), old_public_key)


__all__ = ["canonical", "public_b64", "rotate", "sign", "verify", "verify_rotation"]
