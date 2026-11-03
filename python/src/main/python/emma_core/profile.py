import sqlite3
import json
import os
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from contextlib import contextmanager

DB_PATH = "data/profile.db"


@dataclass
class StudentProfile:
    student_name: str = "Usuario"
    native_language: str = "es"
    target_language: str = "en"
    level: str = "B1"
    vocabulary_known: int = 0
    created_at: str = ""
    updated_at: str = ""
    current_unit: str = ""
    completed_units: List[str] = None
    total_sessions: int = 0
    total_turns: int = 0

    def __post_init__(self):
        if self.completed_units is None:
            self.completed_units = []
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()


class ProfileManager:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    @contextmanager
    def get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        with self.get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS profile (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS errors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    error_type TEXT NOT NULL,
                    original_text TEXT NOT NULL,
                    corrected_text TEXT NOT NULL,
                    explanation TEXT,
                    count INTEGER DEFAULT 1,
                    first_seen TEXT DEFAULT CURRENT_TIMESTAMP,
                    last_seen TEXT DEFAULT CURRENT_TIMESTAMP,
                    is_resolved INTEGER DEFAULT 0
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS vocabulary_srs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    word TEXT NOT NULL,
                    translation TEXT,
                    example TEXT,
                    language TEXT DEFAULT 'en',
                    interval INTEGER DEFAULT 1,
                    ease_factor REAL DEFAULT 2.5,
                    repetitions INTEGER DEFAULT 0,
                    next_review DATE DEFAULT CURRENT_DATE,
                    last_reviewed DATE,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_time TEXT DEFAULT CURRENT_TIMESTAMP,
                    end_time TEXT,
                    turns INTEGER DEFAULT 0,
                    corrections_count INTEGER DEFAULT 0,
                    vocabulary_added INTEGER DEFAULT 0
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS session_summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER,
                    turn INTEGER,
                    user_text TEXT,
                    spoken_response TEXT,
                    corrections_json TEXT,
                    vocabulary_json TEXT,
                    turn_time_ms INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("CREATE INDEX IF NOT EXISTS idx_errors_type ON errors(error_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_vocab_review ON vocabulary_srs(next_review)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_summaries_session ON session_summaries(session_id)")

            conn.commit()

    def get_profile(self) -> StudentProfile:
        with self.get_conn() as conn:
            cursor = conn.execute("SELECT key, value FROM profile")
            data = {row['key']: row['value'] for row in cursor.fetchall()}

            if not data:
                return StudentProfile()

            if 'completed_units' in data:
                try:
                    data['completed_units'] = json.loads(data['completed_units'])
                except:
                    data['completed_units'] = []

            return StudentProfile(**data)

    def save_profile(self, profile: StudentProfile):
        profile.updated_at = datetime.now().isoformat()
        data = asdict(profile)
        data['completed_units'] = json.dumps(profile.completed_units)

        with self.get_conn() as conn:
            for key, value in data.items():
                conn.execute(
                    "INSERT OR REPLACE INTO profile (key, value, updated_at) VALUES (?, ?, ?)",
                    (key, str(value), profile.updated_at)
                )
            conn.commit()

    def add_error(self, error_type: str, original: str, corrected: str, explanation: str = ""):
        with self.get_conn() as conn:
            cursor = conn.execute(
                "SELECT id, count FROM errors WHERE error_type=? AND original_text=? AND corrected_text=?",
                (error_type, original, corrected)
            )
            row = cursor.fetchone()

            now = datetime.now().isoformat()
            if row:
                conn.execute(
                    "UPDATE errors SET count=count+1, last_seen=? WHERE id=?",
                    (now, row['id'])
                )
            else:
                conn.execute("""
                    INSERT INTO errors (error_type, original_text, corrected_text, explanation, first_seen, last_seen)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (error_type, original, corrected, explanation, now, now))
            conn.commit()

    def get_recurring_errors(self, limit: int = 10) -> List[Dict]:
        with self.get_conn() as conn:
            cursor = conn.execute("""
                SELECT error_type, original_text, corrected_text, explanation, count
                FROM errors
                WHERE is_resolved = 0
                ORDER BY count DESC, last_seen DESC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def mark_error_resolved(self, error_id: int):
        with self.get_conn() as conn:
            conn.execute("UPDATE errors SET is_resolved=1 WHERE id=?", (error_id,))
            conn.commit()

    def add_vocabulary_srs(self, word: str, translation: str, example: str, language: str = "en"):
        with self.get_conn() as conn:
            cursor = conn.execute("SELECT id FROM vocabulary_srs WHERE word=? AND language=?", (word, language))
            row = cursor.fetchone()
            now = datetime.now().date().isoformat()

            if not row:
                conn.execute("""
                    INSERT INTO vocabulary_srs (word, translation, example, language, next_review)
                    VALUES (?, ?, ?, ?, ?)
                """, (word, translation, example, language, now))
                conn.commit()

    def get_due_reviews(self, limit: int = 10) -> List[Dict]:
        with self.get_conn() as conn:
            cursor = conn.execute("""
                SELECT word, translation, example, interval, repetitions, ease_factor
                FROM vocabulary_srs
                WHERE date(next_review) <= date('now')
                ORDER BY next_review ASC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def update_srs_after_review(self, word: str, quality: int):
        with self.get_conn() as conn:
            cursor = conn.execute(
                "SELECT interval, repetitions, ease_factor FROM vocabulary_srs WHERE word=?", (word,)
            )
            row = cursor.fetchone()
            if not row:
                return

            interval, reps, ease = row['interval'], row['repetitions'], row['ease_factor']

            if quality < 3:
                reps = 0
                interval = 1
            else:
                if reps == 0:
                    interval = 1
                elif reps == 1:
                    interval = 6
                else:
                    interval = round(interval * item.get('ease_factor', 2.5))
                reps += 1

            ease = max(1.3, ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))

            next_review = (datetime.now() + timedelta(days=interval)).date().isoformat()

            conn.execute("""
                UPDATE vocabulary_srs
                SET interval=?, repetitions=?, ease_factor=?, next_review=?, last_reviewed=date('now')
                WHERE word=?
            """, (interval, reps, ease, next_review, word))
            conn.commit()

    def start_session(self) -> int:
        with self.get_conn() as conn:
            cursor = conn.execute(
                "INSERT INTO sessions (start_time) VALUES (datetime('now'))"
            )
            conn.commit()
            return cursor.lastrowid

    def end_session(self, session_id: int, turns: int, corrections: int, vocab_added: int):
        with self.get_conn() as conn:
            conn.execute("""
                UPDATE sessions
                SET end_time=datetime('now'), turns=?, corrections_count=?, vocabulary_added=?
                WHERE id=?
            """, (turns, corrections, vocab_added, session_id))
            conn.commit()

    def save_turn_summary(self, session_id: int, turn: int, user_text: str,
                          spoken: str, corrections: List, vocabulary: List, turn_time_ms: int):
        with self.get_conn() as conn:
            conn.execute("""
                INSERT INTO session_summaries
                (session_id, turn, user_text, spoken_response, corrections_json, vocabulary_json, turn_time_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (session_id, turn,
                  "user_text", "spoken",
                  json.dumps(corrections), json.dumps(vocabulary),
                  turn_time_ms))
            conn.commit()


# Instancia global
PROFILE_MANAGER = ProfileManager()

def get_profile_manager() -> "ProfileManager":
    return PROFILE_MANAGER