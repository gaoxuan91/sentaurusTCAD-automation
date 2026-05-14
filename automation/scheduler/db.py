"""SQLite database layer for TCAD simulation state management."""

import sqlite3
import threading
from typing import Dict, List, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS batches (
    batch_id     TEXT PRIMARY KEY,
    config_json  TEXT NOT NULL,
    status       TEXT DEFAULT 'created',
    task_total   INTEGER DEFAULT 0,
    task_done    INTEGER DEFAULT 0,
    task_failed  INTEGER DEFAULT 0,
    created_at   TEXT DEFAULT (datetime('now')),
    started_at   TEXT,
    finished_at  TEXT
);

CREATE TABLE IF NOT EXISTS tasks (
    task_id      TEXT PRIMARY KEY,
    batch_id     TEXT NOT NULL,
    case_name    TEXT NOT NULL,
    interface    TEXT NOT NULL,
    bx_nm        INTEGER NOT NULL,
    cmd_path     TEXT NOT NULL,
    plt_path     TEXT,
    log_path     TEXT,
    status       TEXT DEFAULT 'pending',
    photocurrent REAL,
    convergence  INTEGER DEFAULT 0,
    duration_s   REAL,
    retry_count  INTEGER DEFAULT 0,
    error_msg    TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    started_at   TEXT,
    finished_at  TEXT
);

CREATE INDEX IF NOT EXISTS idx_tasks_batch ON tasks(batch_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(batch_id, status);
"""

_local = threading.local()


def get_conn(db_path: str) -> sqlite3.Connection:
    """Get a thread-local connection, reconnecting if closed."""
    key = f"conn_{db_path}"
    if not hasattr(_local, "connections"):
        _local.connections = {}
    conn = _local.connections.get(key)
    if conn is None:
        conn = _make_conn(db_path)
        _local.connections[key] = conn
    else:
        # Check if connection was closed (e.g. by another code path)
        try:
            conn.execute("SELECT 1")
        except sqlite3.ProgrammingError:
            conn = _make_conn(db_path)
            _local.connections[key] = conn
    return conn


def _make_conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_db(db_path: str) -> sqlite3.Connection:
    """Initialize database schema and return a connection."""
    conn = get_conn(db_path)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def create_batch(conn: sqlite3.Connection, batch_id: str, config_json: str, task_count: int) -> None:
    conn.execute(
        "INSERT INTO batches (batch_id, config_json, status, task_total) VALUES (?, ?, 'created', ?)",
        (batch_id, config_json, task_count),
    )
    conn.commit()


def add_tasks(conn: sqlite3.Connection, tasks: List[Dict]) -> None:
    """Insert multiple tasks. Each dict: task_id, batch_id, case_name, interface, bx_nm, cmd_path, plt_path, log_path."""
    for t in tasks:
        conn.execute(
            """INSERT INTO tasks (task_id, batch_id, case_name, interface, bx_nm, cmd_path, plt_path, log_path)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (t["task_id"], t["batch_id"], t["case_name"], t["interface"],
             t["bx_nm"], t["cmd_path"], t.get("plt_path", ""), t.get("log_path", "")),
        )
    conn.commit()


def mark_batch_running(conn: sqlite3.Connection, batch_id: str) -> None:
    conn.execute(
        "UPDATE batches SET status='running', started_at=datetime('now') WHERE batch_id=?",
        (batch_id,),
    )
    conn.commit()


def mark_batch_done(conn: sqlite3.Connection, batch_id: str) -> None:
    conn.execute(
        "UPDATE batches SET status='done', finished_at=datetime('now') WHERE batch_id=?",
        (batch_id,),
    )
    conn.commit()


def mark_batch_failed(conn: sqlite3.Connection, batch_id: str) -> None:
    conn.execute(
        "UPDATE batches SET status='failed', finished_at=datetime('now') WHERE batch_id=?",
        (batch_id,),
    )
    conn.commit()


def claim_next_task(conn: sqlite3.Connection, batch_id: str) -> Optional[Dict]:
    """Atomically claim one pending task. Returns None if none left."""
    cur = conn.execute(
        "SELECT * FROM tasks WHERE batch_id=? AND status='pending' ORDER BY task_id LIMIT 1",
        (batch_id,),
    )
    row = cur.fetchone()
    if row is None:
        return None
    task_id = row["task_id"]
    conn.execute(
        "UPDATE tasks SET status='running', started_at=datetime('now') WHERE task_id=? AND status='pending'",
        (task_id,),
    )
    conn.commit()
    if conn.execute("SELECT changes()").fetchone()[0] == 0:
        return None
    return dict(row)


def mark_task_done(conn: sqlite3.Connection, task_id: str, photocurrent: float,
                   convergence: bool, duration_s: float) -> None:
    conn.execute(
        """UPDATE tasks SET status='done', photocurrent=?, convergence=?,
           duration_s=?, finished_at=datetime('now') WHERE task_id=?""",
        (photocurrent, int(convergence), duration_s, task_id),
    )
    conn.execute(
        "UPDATE batches SET task_done = (SELECT COUNT(*) FROM tasks WHERE batch_id=batches.batch_id AND status='done')",
    )
    conn.commit()


def mark_task_failed(conn: sqlite3.Connection, task_id: str, error_msg: str) -> None:
    conn.execute(
        "UPDATE tasks SET status='failed', error_msg=?, retry_count=retry_count+1, finished_at=datetime('now') WHERE task_id=?",
        (error_msg, task_id),
    )
    conn.execute(
        "UPDATE batches SET task_failed = (SELECT COUNT(*) FROM tasks WHERE batch_id=batches.batch_id AND status='failed')",
    )
    conn.commit()


def reset_task_for_retry(conn: sqlite3.Connection, task_id: str) -> None:
    """Reset a failed task back to pending for retry."""
    conn.execute(
        "UPDATE tasks SET status='pending', started_at=NULL, finished_at=NULL WHERE task_id=?",
        (task_id,),
    )
    conn.commit()


def get_batch_status(conn: sqlite3.Connection, batch_id: str) -> Dict:
    row = conn.execute("SELECT * FROM batches WHERE batch_id=?", (batch_id,)).fetchone()
    if row is None:
        return {}
    d = dict(row)
    pending = conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE batch_id=? AND status='pending'", (batch_id,)
    ).fetchone()[0]
    running = conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE batch_id=? AND status='running'", (batch_id,)
    ).fetchone()[0]
    d["pending"] = pending
    d["running"] = running
    return d


def get_batch_results(conn: sqlite3.Connection, batch_id: str, case: Optional[str] = None) -> List[Dict]:
    query = "SELECT case_name, interface, bx_nm, photocurrent, convergence, duration_s, status, error_msg FROM tasks WHERE batch_id=?"
    params = [batch_id]
    if case:
        query += " AND case_name=?"
        params.append(case)
    query += " ORDER BY case_name, bx_nm"
    return [dict(r) for r in conn.execute(query, params).fetchall()]


def batch_has_pending(conn: sqlite3.Connection, batch_id: str) -> bool:
    n = conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE batch_id=? AND status IN ('pending','running')",
        (batch_id,),
    ).fetchone()[0]
    return n > 0
