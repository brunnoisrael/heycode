"""Repositorio do relay (ADR 0035). SQLite aqui; Postgres em producao atras da mesma interface.

Toda consulta de instalacao filtra por conta: nenhum metodo devolve dado de outra conta.
"""

import sqlite3
import threading
import uuid

_SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
  id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY, account_id TEXT NOT NULL, expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS installations (
  id TEXT PRIMARY KEY, account_id TEXT NOT NULL, public_key TEXT NOT NULL, name TEXT NOT NULL,
  created REAL NOT NULL, last_seen REAL, revoked INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS usage (
  account_id TEXT NOT NULL, day TEXT NOT NULL, n INTEGER NOT NULL, PRIMARY KEY (account_id, day));
"""


class SqliteRepository:
    def __init__(self, path: str = ":memory:") -> None:
        self._lock = threading.RLock()
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        with self._lock:
            self._db.executescript(_SCHEMA)

    # contas
    def create_account(self, email: str, password_hash: str, now: float) -> str | None:
        aid = str(uuid.uuid4())
        try:
            with self._lock, self._db:
                self._db.execute(
                    "INSERT INTO accounts (id, email, password_hash, created) VALUES (?,?,?,?)",
                    (aid, email, password_hash, now),
                )
        except sqlite3.IntegrityError:
            return None
        return aid

    def get_account_by_email(self, email: str) -> dict | None:
        with self._lock:
            row = self._db.execute("SELECT * FROM accounts WHERE email=?", (email,)).fetchone()
        return dict(row) if row else None

    # sessoes
    def create_session(self, token_hash: str, account_id: str, expires: float) -> None:
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO sessions (token_hash, account_id, expires) VALUES (?,?,?)",
                (token_hash, account_id, expires),
            )

    def get_session(self, token_hash: str) -> dict | None:
        with self._lock:
            row = self._db.execute("SELECT * FROM sessions WHERE token_hash=?", (token_hash,)).fetchone()
        return dict(row) if row else None

    def delete_session(self, token_hash: str) -> None:
        with self._lock, self._db:
            self._db.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash,))

    def session_hashes(self) -> list[str]:
        with self._lock:
            return [r["token_hash"] for r in self._db.execute("SELECT token_hash FROM sessions")]

    # instalacoes (sempre por conta)
    def count_installations(self, account_id: str) -> int:
        with self._lock:
            return self._db.execute(
                "SELECT COUNT(*) FROM installations WHERE account_id=? AND revoked=0", (account_id,)
            ).fetchone()[0]

    def create_installation(self, account_id: str, public_key: str, name: str, now: float) -> str:
        iid = str(uuid.uuid4())
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO installations (id, account_id, public_key, name, created) VALUES (?,?,?,?,?)",
                (iid, account_id, public_key, name, now),
            )
        return iid

    def list_installations(self, account_id: str) -> list[dict]:
        with self._lock:
            rows = self._db.execute(
                "SELECT id, name, created, last_seen FROM installations WHERE account_id=? AND revoked=0"
                " ORDER BY created",
                (account_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_installation(self, installation_id: str) -> dict | None:
        """Uso interno do relay (autenticacao do envelope); nunca exposto direto a uma conta."""
        with self._lock:
            row = self._db.execute("SELECT * FROM installations WHERE id=?", (installation_id,)).fetchone()
        return dict(row) if row else None

    def get_owned_installation(self, account_id: str, installation_id: str) -> dict | None:
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM installations WHERE id=? AND account_id=? AND revoked=0",
                (installation_id, account_id),
            ).fetchone()
        return dict(row) if row else None

    def revoke_installation(self, account_id: str, installation_id: str) -> bool:
        with self._lock, self._db:
            cur = self._db.execute(
                "UPDATE installations SET revoked=1 WHERE id=? AND account_id=? AND revoked=0",
                (installation_id, account_id),
            )
        return cur.rowcount == 1

    def touch_installation(self, installation_id: str, now: float) -> None:
        with self._lock, self._db:
            self._db.execute("UPDATE installations SET last_seen=? WHERE id=?", (now, installation_id))

    # cotas
    def bump_usage(self, account_id: str, day: str) -> int:
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO usage (account_id, day, n) VALUES (?,?,1)"
                " ON CONFLICT(account_id, day) DO UPDATE SET n = n + 1",
                (account_id, day),
            )
            return self._db.execute("SELECT n FROM usage WHERE account_id=? AND day=?", (account_id, day)).fetchone()[0]
