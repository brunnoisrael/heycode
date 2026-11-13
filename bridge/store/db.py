"""Store SQLite: politicas, sessoes, aprovacoes e historico (ADR 0003)."""
import json
import sqlite3
import threading
import time

MODES = ("manual", "auto", "decisoes")
DEFAULTS = {"mode": "manual", "report_on_end": False}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS policy (
    agent TEXT NOT NULL, project TEXT NOT NULL,
    mode TEXT, report_on_end INTEGER,
    PRIMARY KEY (agent, project));
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY, agent TEXT, project TEXT, status TEXT,
    detail TEXT, summary TEXT, updated REAL);
CREATE TABLE IF NOT EXISTS approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT, agent TEXT, project TEXT,
    tool TEXT, command TEXT, session_id TEXT, decision TEXT, t REAL);
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, payload TEXT, t REAL);
CREATE TABLE IF NOT EXISTS instructions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT NOT NULL, agent TEXT NOT NULL,
    project TEXT, delivered INTEGER NOT NULL DEFAULT 0, t REAL);
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT, agent TEXT, project TEXT, prompt TEXT, cwd TEXT,
    status TEXT NOT NULL DEFAULT 'rodando', summary TEXT, exit_code INTEGER, pid INTEGER,
    t_start REAL, t_end REAL, reported INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS pin_lock (
    id INTEGER PRIMARY KEY CHECK (id = 1), fails INTEGER NOT NULL, until REAL NOT NULL);
"""

RUN_STATUS = ("rodando", "concluida", "falhou", "cancelada", "interrompida")


class Store:
    def __init__(self, path: str = ":memory:") -> None:
        self._lock = threading.RLock()
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        with self._lock:
            self._db.executescript(_SCHEMA)
            cols = [r["name"] for r in self._db.execute("PRAGMA table_info(runs)")]
            if "reported" not in cols:  # banco criado antes do ADR 0015
                self._db.execute("ALTER TABLE runs ADD COLUMN reported INTEGER NOT NULL DEFAULT 1")
            cols = [r["name"] for r in self._db.execute("PRAGMA table_info(approvals)")]
            if "answer" not in cols:
                self._db.execute("ALTER TABLE approvals ADD COLUMN answer TEXT")
            self._db.commit()

    def close(self) -> None:
        with self._lock:
            self._db.close()

    # politicas
    def get_policy(self, agent, project) -> dict:
        a, p = agent or "", project or ""
        # do mais especifico para o mais geral
        order = [(a, p), ("", p), (a, ""), ("", "")]
        seen, result = set(), dict(DEFAULTS)
        found = {}
        with self._lock:
            for key in order:
                if key in seen:
                    continue
                seen.add(key)
                row = self._db.execute(
                    "SELECT mode, report_on_end FROM policy WHERE agent=? AND project=?",
                    key).fetchone()
                if not row:
                    continue
                if "mode" not in found and row["mode"] is not None:
                    found["mode"] = row["mode"]
                if "report_on_end" not in found and row["report_on_end"] is not None:
                    found["report_on_end"] = bool(row["report_on_end"])
        result.update(found)
        return result

    def set_policy(self, mode=None, report_on_end=None, agent=None, project=None) -> None:
        if mode is not None and mode not in MODES:
            raise ValueError(f"modo invalido: {mode!r}")
        a, p = agent or "", project or ""
        with self._lock:
            self._db.execute(
                "INSERT OR IGNORE INTO policy (agent, project) VALUES (?, ?)", (a, p))
            if mode is not None:
                self._db.execute(
                    "UPDATE policy SET mode=? WHERE agent=? AND project=?", (mode, a, p))
            if report_on_end is not None:
                self._db.execute(
                    "UPDATE policy SET report_on_end=? WHERE agent=? AND project=?",
                    (1 if report_on_end else 0, a, p))
            self._db.commit()

    # sessoes
    def upsert_session(self, session_id, agent, project, status, detail="", summary=None) -> None:
        with self._lock:
            self._db.execute(
                "INSERT INTO sessions (session_id, agent, project, status, detail, summary, updated)"
                " VALUES (?,?,?,?,?,?,?) ON CONFLICT(session_id) DO UPDATE SET"
                " agent=excluded.agent, project=excluded.project, status=excluded.status,"
                " detail=excluded.detail, summary=COALESCE(excluded.summary, sessions.summary),"
                " updated=excluded.updated",
                (session_id, agent, project, status, detail, summary, time.time()))
            self._db.commit()

    def newest_session(self):
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM sessions ORDER BY updated DESC LIMIT 1").fetchone()
        return dict(row) if row else None

    # aprovacoes
    def add_approval(self, agent, project, tool, command, session_id) -> int:
        with self._lock:
            cur = self._db.execute(
                "INSERT INTO approvals (agent, project, tool, command, session_id, decision, t)"
                " VALUES (?,?,?,?,?,NULL,?)",
                (agent, project, tool, command, session_id, time.time()))
            self._db.commit()
            return cur.lastrowid

    def get_approval(self, approval_id: int):
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone()
        return dict(row) if row else None

    def pending_approvals(self) -> list:
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM approvals WHERE decision IS NULL ORDER BY t, id").fetchall()
        return [dict(r) for r in rows]

    def resolve_approval(self, approval_id: int, decision: str) -> None:
        if decision not in ("allow", "deny", "expired"):
            raise ValueError(f"decisao invalida: {decision!r}")
        with self._lock:
            self._db.execute(
                "UPDATE approvals SET decision=? WHERE id=? AND decision IS NULL", (decision, approval_id))
            self._db.commit()

    def answer_question(self, approval_id: int, answer: str, max_age: float) -> bool:
        """Resolve apenas a primeira pergunta ainda válida, em uma operação atômica."""
        with self._lock:
            cur = self._db.execute(
                "UPDATE approvals SET decision='answered', answer=? WHERE id=? AND tool='pedir_resposta'"
                " AND decision IS NULL AND t>? AND id=(SELECT id FROM approvals"
                " WHERE decision IS NULL ORDER BY t, id LIMIT 1)",
                (answer, approval_id, time.time() - max_age))
            self._db.commit()
            return cur.rowcount == 1

    def expire_pending(self) -> int:
        with self._lock:
            cur = self._db.execute(
                "UPDATE approvals SET decision='expired' WHERE decision IS NULL")
            self._db.commit()
            return cur.rowcount

    # fila de instrucoes
    def add_instruction(self, text: str, agent: str = "claude", project: str | None = None) -> int:
        with self._lock:
            cur = self._db.execute(
                "INSERT INTO instructions (text, agent, project, delivered, t) VALUES (?,?,?,0,?)",
                (text, agent, project or None, time.time()))
            self._db.commit()
            return cur.lastrowid

    def pop_instruction(self, agent: str, project: str | None, max_age: float | None = None) -> dict | None:
        """Proxima instrucao do agente/projeto. Com `max_age` (segundos), as mais velhas expiram sem entrega."""
        with self._lock:
            if max_age is not None:  # delivered=2: expirada, nunca entregue (ADR 0018)
                self._db.execute("UPDATE instructions SET delivered=2 WHERE delivered=0 AND t<?",
                                 (time.time() - max_age,))
                self._db.commit()
            row = self._db.execute(
                "SELECT id, text, agent, project FROM instructions WHERE delivered=0 AND agent=?"
                " AND (project IS NULL OR project=?) ORDER BY id LIMIT 1",
                (agent, project or "")).fetchone()
            if not row:
                return None
            self._db.execute("UPDATE instructions SET delivered=1 WHERE id=?", (row["id"],))
            self._db.commit()
            return dict(row)

    # execucoes de agentes (supervisor)
    def create_run(self, agent: str, project: str, prompt: str, cwd: str) -> int:
        with self._lock:
            cur = self._db.execute(
                "INSERT INTO runs (agent, project, prompt, cwd, status, t_start)"
                " VALUES (?,?,?,?,'rodando',?)", (agent, project, prompt, cwd, time.time()))
            self._db.commit()
            return cur.lastrowid

    def update_run(self, run_id: int, status: str | None = None, summary: str | None = None,
                   exit_code: int | None = None, pid: int | None = None) -> None:
        if status is not None and status not in RUN_STATUS:
            raise ValueError(f"status invalido: {status!r}")
        sets, args = [], []
        for col, val in (("status", status), ("summary", summary),
                         ("exit_code", exit_code), ("pid", pid)):
            if val is not None:
                sets.append(f"{col}=?")
                args.append(val)
        if status is not None and status != "rodando":
            sets.append("t_end=?")
            args.append(time.time())
        if not sets:
            return
        with self._lock:
            self._db.execute(f"UPDATE runs SET {', '.join(sets)} WHERE id=?", (*args, run_id))
            self._db.commit()

    def get_run(self, run_id: int) -> dict | None:
        with self._lock:
            row = self._db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        return dict(row) if row else None

    def latest_run(self, agent: str | None = None) -> dict | None:
        with self._lock:
            if agent:
                row = self._db.execute(
                    "SELECT * FROM runs WHERE agent=? ORDER BY id DESC LIMIT 1", (agent,)).fetchone()
            else:
                row = self._db.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 1").fetchone()
        return dict(row) if row else None

    # aviso de fim de ciclo: reported=0 significa "ainda nao falado por voz" (ADR 0015)
    def mark_unreported(self, run_id: int) -> None:
        with self._lock:
            self._db.execute("UPDATE runs SET reported=0 WHERE id=?", (run_id,))
            self._db.commit()

    def mark_reported(self, run_id: int) -> None:
        with self._lock:
            self._db.execute("UPDATE runs SET reported=1 WHERE id=?", (run_id,))
            self._db.commit()

    def first_unreported(self) -> dict | None:
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM runs WHERE reported=0 AND status!='interrompida' ORDER BY id LIMIT 1"
            ).fetchone()
        return dict(row) if row else None

    def latest_running(self) -> dict | None:
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM runs WHERE status='rodando' ORDER BY id DESC LIMIT 1").fetchone()
        return dict(row) if row else None

    # trava de PIN
    def get_pin_lock(self) -> dict:
        with self._lock:
            row = self._db.execute("SELECT fails, until FROM pin_lock WHERE id=1").fetchone()
        return {"fails": row["fails"], "until": row["until"]} if row else {"fails": 0, "until": 0.0}

    def set_pin_lock(self, fails: int, until: float) -> None:
        with self._lock:
            self._db.execute(
                "INSERT INTO pin_lock (id, fails, until) VALUES (1,?,?) ON CONFLICT(id) DO UPDATE"
                " SET fails=excluded.fails, until=excluded.until", (fails, until))
            self._db.commit()

    def interrupt_running(self) -> int:
        with self._lock:
            cur = self._db.execute(
                "UPDATE runs SET status='interrompida', reported=1, t_end=? WHERE status='rodando'",
                (time.time(),))
            self._db.commit()
            return cur.rowcount

    # historico
    def log(self, kind: str, payload: dict) -> None:
        with self._lock:
            self._db.execute(
                "INSERT INTO history (kind, payload, t) VALUES (?,?,?)",
                (kind, json.dumps(payload, default=str), time.time()))
            self._db.commit()
