import json
import sqlite3
import threading
from datetime import datetime, timezone


class _LockedConn:
    """Envuelve la conexion SQLite con un lock para uso multi-hilo."""

    def __init__(self, conn, lock):
        self._c = conn
        self._lock = lock

    def execute(self, *a, **kw):
        with self._lock:
            return self._c.execute(*a, **kw)

    def executescript(self, *a, **kw):
        with self._lock:
            return self._c.executescript(*a, **kw)

    def commit(self):
        with self._lock:
            return self._c.commit()

    def __enter__(self):
        self._lock.acquire()
        return self._c

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type is None:
                self._c.commit()
        finally:
            self._lock.release()
        return False

    def __getattr__(self, name):
        return getattr(self._c, name)

SCHEMA = """
CREATE TABLE IF NOT EXISTS learner (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    name TEXT NOT NULL,
    level TEXT NOT NULL,
    native_language TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    mode TEXT NOT NULL,
    topic TEXT,
    summary TEXT
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    corrections TEXT,
    ts TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS vocab (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    word TEXT NOT NULL UNIQUE,
    translation TEXT,
    example TEXT,
    ease REAL NOT NULL DEFAULT 2.5,
    interval_days REAL NOT NULL DEFAULT 0,
    repetitions INTEGER NOT NULL DEFAULT 0,
    next_review TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    error_type TEXT,
    original TEXT,
    corrected TEXT,
    explanation TEXT,
    ts TEXT NOT NULL
);
"""


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        raw = sqlite3.connect(str(path), check_same_thread=False)
        raw.row_factory = sqlite3.Row
        raw.executescript(SCHEMA)
        raw.commit()
        self.conn = _LockedConn(raw, self._lock)

    def ensure_learner(self, name, level, native_language):
        row = self.conn.execute("SELECT * FROM learner WHERE id = 1").fetchone()
        if row is None:
            self.conn.execute(
                "INSERT INTO learner (id, name, level, native_language, created_at, updated_at) VALUES (1, ?, ?, ?, ?, ?)",
                (name, level, native_language, now(), now()),
            )
            self.conn.commit()
            row = self.conn.execute("SELECT * FROM learner WHERE id = 1").fetchone()
        return dict(row)

    def learner(self):
        row = self.conn.execute("SELECT * FROM learner WHERE id = 1").fetchone()
        return dict(row) if row else None

    def set_level(self, level):
        self.conn.execute(
            "UPDATE learner SET level = ?, updated_at = ? WHERE id = 1", (level, now())
        )
        self.conn.commit()

    def start_session(self, mode):
        cur = self.conn.execute(
            "INSERT INTO sessions (started_at, mode) VALUES (?, ?)", (now(), mode)
        )
        self.conn.commit()
        return cur.lastrowid

    def end_session(self, session_id, topic, summary):
        self.conn.execute(
            "UPDATE sessions SET ended_at = ?, topic = ?, summary = ? WHERE id = ?",
            (now(), topic, summary, session_id),
        )
        self.conn.commit()

    def add_message(self, session_id, role, content, corrections=None):
        self.conn.execute(
            "INSERT INTO messages (session_id, role, content, corrections, ts) VALUES (?, ?, ?, ?, ?)",
            (
                session_id,
                role,
                content,
                json.dumps(corrections, ensure_ascii=False) if corrections else None,
                now(),
            ),
        )
        self.conn.commit()

    def log_corrections(self, corrections):
        for c in corrections or []:
            self.conn.execute(
                "INSERT INTO errors (error_type, original, corrected, explanation, ts) VALUES (?, ?, ?, ?, ?)",
                (c.get("type"), c.get("original"), c.get("corrected"), c.get("explanation"), now()),
            )
        self.conn.commit()

    def recent_error_types(self, limit=5):
        rows = self.conn.execute(
            "SELECT error_type, COUNT(*) AS n FROM errors GROUP BY error_type ORDER BY n DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def add_vocab(self, word, translation, example):
        word = (word or "").strip()
        if not word:
            return
        existing = self.conn.execute(
            "SELECT id FROM vocab WHERE lower(word) = lower(?)", (word,)
        ).fetchone()
        if existing:
            return
        self.conn.execute(
            "INSERT INTO vocab (word, translation, example, next_review, created_at) VALUES (?, ?, ?, ?, ?)",
            (word, translation, example, now(), now()),
        )
        self.conn.commit()

    def due_vocab(self, limit=20):
        rows = self.conn.execute(
            "SELECT * FROM vocab WHERE next_review IS NULL OR next_review <= ? ORDER BY next_review ASC LIMIT ?",
            (now(), limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def update_vocab(self, vocab_id, ease, interval_days, repetitions, next_review):
        self.conn.execute(
            "UPDATE vocab SET ease = ?, interval_days = ?, repetitions = ?, next_review = ? WHERE id = ?",
            (ease, interval_days, repetitions, next_review, vocab_id),
        )
        self.conn.commit()

    def vocab_stats(self):
        total = self.conn.execute("SELECT COUNT(*) FROM vocab").fetchone()[0]
        due = len(self.due_vocab(limit=9999))
        learned = self.conn.execute(
            "SELECT COUNT(*) FROM vocab WHERE repetitions >= 3"
        ).fetchone()[0]
        return {"total": total, "due": due, "learned": learned}

    def session_count(self):
        return self.conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]

    def last_session_summary(self):
        row = self.conn.execute(
            "SELECT topic, summary FROM sessions WHERE summary IS NOT NULL ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None

    def last_errors(self, limit=8):
        rows = self.conn.execute(
            "SELECT error_type, original, corrected, explanation FROM errors ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
