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
CREATE TABLE IF NOT EXISTS oauth_codes (
  code_hash TEXT PRIMARY KEY, account_id TEXT NOT NULL, client_id TEXT NOT NULL, redirect_uri TEXT NOT NULL,
  challenge TEXT, expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS oauth_tokens (
  token_hash TEXT PRIMARY KEY, kind TEXT NOT NULL, account_id TEXT NOT NULL, client_id TEXT NOT NULL,
  family TEXT NOT NULL, expires REAL NOT NULL, used INTEGER NOT NULL DEFAULT 0);
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

    # OAuth2 (ADR 0041): tudo guardado como hash
    def put_oauth_code(
        self, code_hash: str, account_id: str, client_id: str, redirect_uri: str, challenge: str | None, expires: float
    ) -> None:
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO oauth_codes VALUES (?,?,?,?,?,?)",
                (code_hash, account_id, client_id, redirect_uri, challenge, expires),
            )

    def pop_oauth_code(self, code_hash: str) -> dict | None:
        """Le e apaga numa so operacao: o codigo vale uma vez."""
        with self._lock, self._db:
            row = self._db.execute("SELECT * FROM oauth_codes WHERE code_hash=?", (code_hash,)).fetchone()
            if row is None:
                return None
            self._db.execute("DELETE FROM oauth_codes WHERE code_hash=?", (code_hash,))
        return dict(row)

    def put_oauth_token(
        self, token_hash: str, kind: str, account_id: str, client_id: str, family: str, expires: float
    ) -> None:
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO oauth_tokens (token_hash, kind, account_id, client_id, family, expires)"
                " VALUES (?,?,?,?,?,?)",
                (token_hash, kind, account_id, client_id, family, expires),
            )

    def get_oauth_token(self, token_hash: str) -> dict | None:
        with self._lock:
            row = self._db.execute("SELECT * FROM oauth_tokens WHERE token_hash=?", (token_hash,)).fetchone()
        return dict(row) if row else None

    def mark_oauth_token_used(self, token_hash: str) -> bool:
        """True so para quem de fato a marcou (evita duas trocas simultaneas do mesmo refresh)."""
        with self._lock, self._db:
            cur = self._db.execute("UPDATE oauth_tokens SET used=1 WHERE token_hash=? AND used=0", (token_hash,))
        return cur.rowcount == 1

    def revoke_oauth_family(self, family: str) -> None:
        with self._lock, self._db:
            self._db.execute("DELETE FROM oauth_tokens WHERE family=?", (family,))

    def revoke_oauth_account(self, account_id: str) -> None:
        with self._lock, self._db:
            self._db.execute("DELETE FROM oauth_tokens WHERE account_id=?", (account_id,))
            self._db.execute("DELETE FROM oauth_codes WHERE account_id=?", (account_id,))

    def dump_oauth_hashes(self) -> list[str]:
        with self._lock:
            return [r[0] for r in self._db.execute("SELECT token_hash FROM oauth_tokens")]
