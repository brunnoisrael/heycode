"""Ponto de entrada do relay: `uvicorn heycode.relay.main:app` (variaveis de ambiente, sem segredos no codigo)."""

import os
import time
from collections.abc import Mapping

from heycode.relay.app import DAILY_QUOTA, SYNC_TIMEOUT, create_app
from heycode.relay.repo import SqliteRepository


def build_app(env: Mapping[str, str]):
    """RELAY_DB (obrigatorio: caminho do SQLite num volume persistente), RELAY_DAILY_QUOTA, RELAY_SYNC_TIMEOUT."""
    db = env.get("RELAY_DB")
    if not db:
        raise RuntimeError("defina RELAY_DB com o caminho do banco (volume persistente); sem ele os dados se perderiam")
    return create_app(
        SqliteRepository(db),
        time.time,
        daily_quota=int(env.get("RELAY_DAILY_QUOTA", DAILY_QUOTA)),
        sync_timeout=float(env.get("RELAY_SYNC_TIMEOUT", SYNC_TIMEOUT)),
    )


def __getattr__(name: str):  # `app` so e criado quando o uvicorn o pede, nunca ao importar o modulo
    if name == "app":
        return build_app(os.environ)
    raise AttributeError(name)
