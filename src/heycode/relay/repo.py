"""Repositorio do relay (ADR 0035). SQLite aqui; Postgres em producao atras da mesma interface.

Toda consulta de instalacao filtra por conta: nenhum metodo devolve dado de outra conta.
"""

import json
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
CREATE TABLE IF NOT EXISTS devices (
  account_id TEXT NOT NULL, installation_id TEXT NOT NULL, device_id TEXT NOT NULL,
  status TEXT NOT NULL, created REAL NOT NULL, PRIMARY KEY (account_id, installation_id, device_id));
CREATE TABLE IF NOT EXISTS account_settings (account_id TEXT PRIMARY KEY, default_installation TEXT);
CREATE TABLE IF NOT EXISTS shortcuts (
  id TEXT PRIMARY KEY, account_id TEXT NOT NULL, name TEXT NOT NULL, aliases TEXT NOT NULL,
  agent TEXT NOT NULL, project TEXT, instruction TEXT NOT NULL, description TEXT,
  enabled INTEGER NOT NULL DEFAULT 1, created REAL NOT NULL);
CREATE INDEX IF NOT EXISTS shortcuts_account ON shortcuts (account_id);
CREATE TABLE IF NOT EXISTS audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT, account_id TEXT NOT NULL, t REAL NOT NULL, kind TEXT NOT NULL,
  installation_id TEXT, device_id TEXT, result TEXT NOT NULL, label TEXT);
CREATE INDEX IF NOT EXISTS audit_account ON audit (account_id, id);
CREATE TABLE IF NOT EXISTS usage (
  account_id TEXT NOT NULL, day TEXT NOT NULL, n INTEGER NOT NULL, PRIMARY KEY (account_id, day));
CREATE TABLE IF NOT EXISTS plans (
  account_id TEXT PRIMARY KEY, plan TEXT NOT NULL DEFAULT 'livre', interest TEXT, updated REAL NOT NULL);
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

    def get_account_email(self, account_id: str) -> str | None:
        with self._lock:
            row = self._db.execute("SELECT email FROM accounts WHERE id=?", (account_id,)).fetchone()
        return row[0] if row else None

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

    def rename_installation(self, account_id: str, installation_id: str, name: str) -> dict | None:
        with self._lock, self._db:
            cur = self._db.execute(
                "UPDATE installations SET name=? WHERE id=? AND account_id=? AND revoked=0",
                (name, installation_id, account_id),
            )
        if cur.rowcount != 1:
            return None
        return self.get_owned_installation(account_id, installation_id)

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

    def get_usage(self, account_id: str, day: str) -> int:
        with self._lock:
            row = self._db.execute("SELECT n FROM usage WHERE account_id=? AND day=?", (account_id, day)).fetchone()
        return row[0] if row else 0

    # niveis de apoio (ADR 0059): o nivel so muda por comando no servidor; o interesse, pela propria conta
    def get_plan(self, account_id: str) -> dict:
        with self._lock:
            row = self._db.execute("SELECT plan, interest FROM plans WHERE account_id=?", (account_id,)).fetchone()
        return {"plan": row["plan"], "interest": row["interest"]} if row else {"plan": "livre", "interest": None}

    def _set_plan_field(self, account_id: str, column: str, value: str | None, now: float) -> None:
        with self._lock, self._db:
            self._db.execute("INSERT OR IGNORE INTO plans (account_id, updated) VALUES (?,?)", (account_id, now))
            self._db.execute(f"UPDATE plans SET {column}=?, updated=? WHERE account_id=?", (value, now, account_id))

    def set_plan(self, account_id: str, plan: str, now: float) -> None:
        self._set_plan_field(account_id, "plan", plan, now)  # nome de coluna fixo

    def set_plan_interest(self, account_id: str, interest: str | None, now: float) -> None:
        self._set_plan_field(account_id, "interest", interest, now)  # nome de coluna fixo

    def list_plan_interest(self) -> list[dict]:
        """Quem pediu para apoiar (uso do dono, no servidor): e-mail, nivel atual e nivel desejado."""
        sql = (
            "SELECT a.email, p.plan, p.interest, p.updated FROM plans p JOIN accounts a ON a.id = p.account_id"
            " WHERE p.interest IS NOT NULL ORDER BY p.updated"
        )
        with self._lock:
            return [dict(r) for r in self._db.execute(sql)]

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

    # dispositivos e instalacao padrao (ADR 0043): tudo filtrado por conta
    def set_default_installation(self, account_id: str, installation_id: str) -> None:
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO account_settings VALUES (?,?) ON CONFLICT(account_id) DO UPDATE SET"
                " default_installation=excluded.default_installation",
                (account_id, installation_id),
            )

    def get_default_installation(self, account_id: str) -> str | None:
        with self._lock:
            row = self._db.execute(
                "SELECT default_installation FROM account_settings WHERE account_id=?", (account_id,)
            ).fetchone()
        return row[0] if row else None

    def device_status(self, account_id: str, installation_id: str, device_id: str) -> str | None:
        with self._lock:
            row = self._db.execute(
                "SELECT status FROM devices WHERE account_id=? AND installation_id=? AND device_id=?",
                (account_id, installation_id, device_id),
            ).fetchone()
        return row[0] if row else None

    def add_pending_device(
        self, account_id: str, installation_id: str, device_id: str, now: float, max_pending: int
    ) -> bool:
        """Registra a solicitacao; False se a conta ja tem o maximo de pendentes."""
        with self._lock, self._db:
            pending = self._db.execute(
                "SELECT COUNT(*) FROM devices WHERE account_id=? AND status='pending'", (account_id,)
            ).fetchone()[0]
            if pending >= max_pending:
                return False
            self._db.execute(
                "INSERT OR IGNORE INTO devices VALUES (?,?,?,'pending',?)",
                (account_id, installation_id, device_id, now),
            )
        return True

    def list_devices(self, account_id: str) -> list[dict]:
        with self._lock:
            rows = self._db.execute(
                "SELECT installation_id, device_id, status FROM devices WHERE account_id=? ORDER BY created",
                (account_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def approve_device(self, account_id: str, installation_id: str, device_id: str) -> bool:
        with self._lock, self._db:
            cur = self._db.execute(
                "UPDATE devices SET status='approved' WHERE account_id=? AND installation_id=? AND device_id=?"
                " AND status='pending'",
                (account_id, installation_id, device_id),
            )
        return cur.rowcount == 1

    def remove_device(self, account_id: str, installation_id: str, device_id: str, status: str | None = None) -> bool:
        sql = "DELETE FROM devices WHERE account_id=? AND installation_id=? AND device_id=?"
        args: tuple = (account_id, installation_id, device_id)
        if status:
            sql += " AND status=?"
            args += (status,)
        with self._lock, self._db:
            return self._db.execute(sql, args).rowcount == 1

    def delete_account(self, account_id: str) -> list[str]:
        """Apaga a conta e tudo dela; devolve os ids das instalacoes para derrubar as conexoes (LGPD)."""
        with self._lock, self._db:
            ids = [r[0] for r in self._db.execute("SELECT id FROM installations WHERE account_id=?", (account_id,))]
            for table in (
                "shortcuts",
                "audit",
                "sessions",
                "installations",
                "devices",
                "account_settings",
                "usage",
                "plans",
                "oauth_tokens",
                "oauth_codes",
            ):
                self._db.execute(f"DELETE FROM {table} WHERE account_id=?", (account_id,))  # nomes fixos
            self._db.execute("DELETE FROM accounts WHERE id=?", (account_id,))
        return ids

    # rastro (ADR 0047): so metadados, nunca conteudo
    AUDIT_RETENTION = 30 * 86400.0

    def add_audit(
        self,
        account_id: str,
        t: float,
        kind: str,
        result: str,
        installation_id: str | None = None,
        device_id: str | None = None,
        label: str | None = None,
    ) -> None:
        with self._lock, self._db:
            self._db.execute("DELETE FROM audit WHERE t < ?", (t - self.AUDIT_RETENTION,))  # retencao de 30 dias
            self._db.execute(
                "INSERT INTO audit (account_id, t, kind, installation_id, device_id, result, label)"
                " VALUES (?,?,?,?,?,?,?)",
                (account_id, t, kind[:80], installation_id, device_id, result, label),
            )

    def list_audit(
        self,
        account_id: str,
        limit: int,
        before: int | None = None,
        installation_id: str | None = None,
        device_id: str | None = None,
        result: str | None = None,
    ) -> list[dict]:
        sql = "SELECT id, t, kind, installation_id, device_id, result, label FROM audit WHERE account_id=?"
        args: list = [account_id]
        for column, value in (("installation_id", installation_id), ("device_id", device_id), ("result", result)):
            if value:
                sql += f" AND {column}=?"  # nomes de coluna fixos acima
                args.append(value)
        if before:
            sql += " AND id < ?"
            args.append(before)
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        with self._lock:
            return [dict(r) for r in self._db.execute(sql, args).fetchall()]

    def count_audit(self) -> int:
        with self._lock:
            return self._db.execute("SELECT COUNT(*) FROM audit").fetchone()[0]

    # atalhos para agentes (ADR 0048, fase A)
    @staticmethod
    def _shortcut(row) -> dict:
        d = dict(row)
        d["aliases"] = json.loads(d["aliases"])
        d["enabled"] = bool(d["enabled"])
        d.pop("account_id", None)
        return d

    def list_shortcuts(self, account_id: str) -> list[dict]:
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM shortcuts WHERE account_id=? ORDER BY created, id", (account_id,)
            ).fetchall()
        return [self._shortcut(r) for r in rows]

    def count_shortcuts(self, account_id: str | None = None) -> int:
        with self._lock:
            if account_id is None:
                return self._db.execute("SELECT COUNT(*) FROM shortcuts").fetchone()[0]
            return self._db.execute("SELECT COUNT(*) FROM shortcuts WHERE account_id=?", (account_id,)).fetchone()[0]

    def create_shortcut(self, account_id: str, fields: dict, now: float) -> dict:
        sid = str(uuid.uuid4())
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO shortcuts (id, account_id, name, aliases, agent, project, instruction, description,"
                " enabled, created) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    sid,
                    account_id,
                    fields["name"],
                    json.dumps(fields["aliases"]),
                    fields["agent"],
                    fields["project"],
                    fields["instruction"],
                    fields["description"],
                    int(fields["enabled"]),
                    now,
                ),
            )
        return next(s for s in self.list_shortcuts(account_id) if s["id"] == sid)

    def update_shortcut(self, account_id: str, shortcut_id: str, fields: dict) -> dict | None:
        with self._lock, self._db:
            cur = self._db.execute(
                "UPDATE shortcuts SET name=?, aliases=?, agent=?, project=?, instruction=?, description=?, enabled=?"
                " WHERE id=? AND account_id=?",
                (
                    fields["name"],
                    json.dumps(fields["aliases"]),
                    fields["agent"],
                    fields["project"],
                    fields["instruction"],
                    fields["description"],
                    int(fields["enabled"]),
                    shortcut_id,
                    account_id,
                ),
            )
        if cur.rowcount != 1:
            return None
        return next(s for s in self.list_shortcuts(account_id) if s["id"] == shortcut_id)

    def delete_shortcut(self, account_id: str, shortcut_id: str) -> dict | None:
        found = next((s for s in self.list_shortcuts(account_id) if s["id"] == shortcut_id), None)
        if found is None:
            return None
        with self._lock, self._db:
            self._db.execute("DELETE FROM shortcuts WHERE id=? AND account_id=?", (shortcut_id, account_id))
        return found
