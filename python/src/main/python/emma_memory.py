#!/usr/bin/env python3
"""Memoria estructurada de Emma en un unico SQLite (data/emma.db).

Cuatro capas:

  1. profile  -> nivel MCER, objetivos, intereses y errores frecuentes.
  2. errors / vocab -> repeticion espaciada (veces_fallado, proxima_revision).
  3. tools    -> get_profile, save_error, save_vocab, get_due_reviews,
                 search_sessions. Descripciones cortas y argumentos validados.
  4. sessions -> turnos + consolidacion al cerrar la sesion con JSON validado
                 por codigo (nunca se confia en que el modelo guarde solo).

El historial largo no se inyecta en el prompt: solo el perfil (menos de 500
tokens) y, en el primer turno, los repasos pendientes. El resto se consulta
bajo demanda con search_sessions.

Se puede probar por separado:

    python emma_memory.py              # resumen de la memoria
    python emma_memory.py --migrate    # importa memoria_emma.json / emma_learning.json
    python emma_memory.py --selftest   # pruebas de SRS, busqueda y validacion
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
import unicodedata
import urllib.request
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Configuracion
# ---------------------------------------------------------------------------

DB_PATH = "data/emma.db"
LEGACY_MEMORY = "memoria_emma.json"
LEGACY_LEARNING = "emma_learning.json"

MAX_PROFILE_CHARS = 1600          # ~400 tokens
MAX_TRANSCRIPT_CHARS = 7000       # material para consolidar
MAX_ITEM_CHARS = 160
MAX_EXPLANATION_CHARS = 300
MAX_EXAMPLE_CHARS = 240
MAX_SUMMARY_CHARS = 700

LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2")

PROFILE_DEFAULTS: Dict[str, str] = {
    "user_name": "",
    "level": "",
    "goals": "",
    "interests": "",
    "native_language": "es",
    "target_language": "en",
    "notes": "",
    "last_summary": "",
}


# ---------------------------------------------------------------------------
# Utilidades de texto
# ---------------------------------------------------------------------------

_DIACRITICS = str.maketrans(
    "áéíóúüñÁÉÍÓÚÜÑ", "aeiouunAEIOUUN"
)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().lower().translate(_DIACRITICS)


def _clean(text: Any, limit: int = MAX_ITEM_CHARS) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip().strip(' "\'.,;')
    return value[:limit]


def _is_latin(text: str) -> bool:
    for char in str(text or ""):
        if not char.isalpha():
            continue
        code = ord(char)
        if char.isascii() or 0x00C0 <= code <= 0x024F:
            continue
        return False
    return True


_WORD_RE = re.compile(r"[a-z0-9']+", re.IGNORECASE)

_EN_HINTS = {
    "the", "a", "an", "is", "are", "was", "were", "have", "has", "had",
    "do", "does", "did", "i", "you", "he", "she", "it", "we", "they",
    "my", "your", "his", "her", "our", "their", "to", "of", "in", "on",
    "and", "but", "because", "what", "why", "how", "this", "that",
}
_ES_HINTS = {
    "el", "la", "los", "las", "un", "una", "es", "son", "era", "eran",
    "he", "has", "ha", "hemos", "han", "yo", "tu", "tú", "el", "ella",
    "nosotros", "ellos", "mi", "mis", "tu", "tus", "su", "sus", "de",
    "del", "en", "y", "pero", "porque", "que", "qué", "como", "cómo",
    "este", "esta", "esto", "eso", "para", "con", "sin",
}


def _language_hint(text: str) -> Optional[str]:
    words = _tokens(text)
    if not words:
        return None
    en = len(words & _EN_HINTS)
    es = len(words & _ES_HINTS)
    if en > es and en >= 2:
        return "en"
    if es > en and es >= 2:
        return "es"
    return None


def _same_language(original: str, corrected: str) -> bool:
    """Descarta traducciones disfrazadas de correccion (EN -> ES o viceversa)."""
    first = _language_hint(original)
    second = _language_hint(corrected)
    if first and second and first != second:
        return False
    return True


def _tokens(text: str) -> set:
    return set(_WORD_RE.findall(_norm(text)))


def _shares_words(original: str, user_text: str) -> bool:
    """Evita guardar correcciones que el usuario nunca dijo."""
    if not user_text:
        return True
    wanted = _tokens(original)
    if not wanted:
        return False
    said = _tokens(user_text)
    if len(wanted) >= 3:
        return len(wanted & said) / len(wanted) >= 0.4
    return wanted.issubset(said)


def _today() -> str:
    return date.today().isoformat()


def _days_from_now(days: int) -> str:
    return (date.today() + timedelta(days=max(0, int(days)))).isoformat()


# ---------------------------------------------------------------------------
# Conexion y esquema
# ---------------------------------------------------------------------------

class MemoryStore:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
            db.commit()
        finally:
            db.close()

    def _init_db(self) -> None:
        with self.connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS profile (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS errors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item TEXT NOT NULL,
                    corrected TEXT NOT NULL DEFAULT '',
                    explanation TEXT NOT NULL DEFAULT '',
                    example TEXT NOT NULL DEFAULT '',
                    kind TEXT NOT NULL DEFAULT 'grammar',
                    language TEXT NOT NULL DEFAULT 'es',
                    times_failed INTEGER NOT NULL DEFAULT 1,
                    times_ok INTEGER NOT NULL DEFAULT 0,
                    interval INTEGER NOT NULL DEFAULT 1,
                    ease REAL NOT NULL DEFAULT 2.5,
                    next_review TEXT NOT NULL DEFAULT (date('now')),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(item, corrected)
                );

                CREATE TABLE IF NOT EXISTS vocab (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    word TEXT NOT NULL,
                    translation TEXT NOT NULL DEFAULT '',
                    example TEXT NOT NULL DEFAULT '',
                    language TEXT NOT NULL DEFAULT 'en',
                    times_seen INTEGER NOT NULL DEFAULT 1,
                    times_failed INTEGER NOT NULL DEFAULT 0,
                    times_ok INTEGER NOT NULL DEFAULT 0,
                    interval INTEGER NOT NULL DEFAULT 1,
                    ease REAL NOT NULL DEFAULT 2.5,
                    next_review TEXT NOT NULL DEFAULT (date('now')),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(word, language)
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    ended_at TEXT,
                    turns INTEGER NOT NULL DEFAULT 0,
                    corrections INTEGER NOT NULL DEFAULT 0,
                    vocab_added INTEGER NOT NULL DEFAULT 0,
                    summary TEXT NOT NULL DEFAULT '',
                    topics TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    turn INTEGER NOT NULL DEFAULT 0,
                    user_text TEXT NOT NULL DEFAULT '',
                    assistant_text TEXT NOT NULL DEFAULT '',
                    language TEXT NOT NULL DEFAULT 'es',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS turns_fts USING fts5(
                    user_text,
                    assistant_text,
                    tokenize = 'unicode61 remove_diacritics 2'
                );

                -- FTS5 para sesiones con trigger automatico (como tutor_memory)
                CREATE VIRTUAL TABLE IF NOT EXISTS sessions_fts USING fts5(
                    summary, topics, content='sessions', content_rowid='id'
                );
                CREATE TRIGGER IF NOT EXISTS sessions_ai AFTER INSERT ON sessions BEGIN
                    INSERT INTO sessions_fts (rowid, summary, topics)
                    VALUES (new.id, new.summary, new.topics);
                END;
                CREATE TRIGGER IF NOT EXISTS sessions_au AFTER UPDATE ON sessions BEGIN
                    INSERT INTO sessions_fts (rowid, summary, topics)
                    VALUES (new.id, new.summary, new.topics);
                END;
                CREATE TRIGGER IF NOT EXISTS sessions_ad AFTER DELETE ON sessions BEGIN
                    INSERT INTO sessions_fts (rowid, summary, topics)
                    VALUES (old.id, old.summary, old.topics);
                END;

                CREATE TABLE IF NOT EXISTS migrations (
                    name TEXT PRIMARY KEY,
                    completed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_errors_due ON errors(next_review);
                CREATE INDEX IF NOT EXISTS idx_vocab_due ON vocab(next_review);
                CREATE INDEX IF NOT EXISTS idx_turns_session ON turns(session_id);
                CREATE INDEX IF NOT EXISTS idx_sessions_open ON sessions(ended_at);
                """
            )

    # -- perfil -------------------------------------------------------------

    def get_profile(self) -> Dict[str, str]:
        profile = dict(PROFILE_DEFAULTS)
        with self.connect() as db:
            for row in db.execute("SELECT key, value FROM profile"):
                profile[str(row["key"])] = str(row["value"])
        return profile

    def set_profile_value(self, key: str, value: Any) -> Dict[str, str]:
        key = _clean(key, 40)
        if not key:
            return self.get_profile()
        text = _clean(value, 500)
        if key == "level":
            text = text.upper()
            if text not in LEVELS:
                return self.get_profile()
        with self.connect() as db:
            db.execute(
                """INSERT INTO profile(key, value, updated_at)
                   VALUES (?, ?, datetime('now'))
                   ON CONFLICT(key) DO UPDATE SET
                       value=excluded.value, updated_at=datetime('now')""",
                (key, text),
            )
        return self.get_profile()

    def get_user_name(self) -> str:
        """Nombre del usuario. SQLite es la fuente unica."""
        return str(self.get_profile().get("user_name") or "").strip()

    def set_user_name(self, name: Any) -> str:
        """Guarda el nombre del usuario en el perfil SQLite."""
        cleaned = _clean(name, 60).strip(" .,!?\"'")
        if not cleaned or not _is_latin(cleaned):
            return self.get_user_name()
        self.set_profile_value("user_name", cleaned)
        return cleaned

    def clear_user_name(self) -> None:
        """Olvida el nombre guardado (correccion explicita del usuario)."""
        self.set_profile_value("user_name", "")

    def merge_interests(self, items: Iterable[str], limit: int = 8) -> List[str]:
        existing = [
            item.strip()
            for item in str(self.get_profile().get("interests") or "").split(",")
            if item.strip()
        ]
        merged = list(existing)
        for item in items:
            cleaned = _clean(item, 60)
            if not cleaned:
                continue
            if _norm(cleaned) not in {_norm(x) for x in merged}:
                merged.append(cleaned)
        merged = merged[:limit]
        self.set_profile_value("interests", ", ".join(merged))
        return merged

    # -- errores / vocabulario (SRS) ---------------------------------------

    def _lookup_error(self, db, item: str, corrected: str):
        return db.execute(
            "SELECT * FROM errors WHERE item=? AND corrected=?",
            (item, corrected),
        ).fetchone()

    def save_error(
        self,
        item: str,
        corrected: str = "",
        explanation: str = "",
        example: str = "",
        kind: str = "grammar",
        language: str = "es",
        increment: bool = True,
    ) -> Optional[Dict[str, Any]]:
        item = _clean(item)
        corrected = _clean(corrected)
        if not item and not corrected:
            return None
        if not _is_latin(item) or not _is_latin(corrected):
            return None
        if item and corrected and _norm(item) == _norm(corrected):
            return None
        if item and corrected and not _same_language(item, corrected):
            return None
        explanation = _clean(explanation, MAX_EXPLANATION_CHARS)
        example = _clean(example, MAX_EXAMPLE_CHARS)
        kind = kind if kind in ("grammar", "vocabulary", "pronunciation") else "grammar"

        with self.connect() as db:
            # ON CONFLICT upsert (tutor_memory style): insert or update atomically
            if increment:
                db.execute(
                    """INSERT INTO errors
                           (item, corrected, explanation, example, kind, language,
                            times_failed, interval, next_review, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, 1, 1, ?, datetime('now'))
                       ON CONFLICT(item, corrected) DO UPDATE SET
                           times_failed = times_failed + 1,
                           explanation = CASE WHEN ?<>'' THEN ? ELSE explanation END,
                           example = CASE WHEN ?<>'' THEN ? ELSE example END,
                           interval = 1,
                           next_review = ?,
                           updated_at = datetime('now')""",
                    (item, corrected, explanation, example, kind, language,
                     _days_from_now(1),
                     explanation, explanation, example, example,
                     _days_from_now(1)),
                )
            else:
                db.execute(
                    """INSERT INTO errors
                           (item, corrected, explanation, example, kind, language,
                            times_failed, interval, next_review, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, 1, 1, ?, datetime('now'))
                       ON CONFLICT(item, corrected) DO UPDATE SET
                           explanation = CASE WHEN explanation='' THEN ? ELSE explanation END,
                           example = CASE WHEN example='' THEN ? ELSE example END,
                           updated_at = datetime('now')""",
                    (item, corrected, explanation, example, kind, language,
                     _days_from_now(1),
                     explanation, example),
                )
            row = db.execute(
                "SELECT * FROM errors WHERE item=? AND corrected=?",
                (item, corrected),
            ).fetchone()
        return dict(row) if row else None

    def save_vocab(
        self,
        word: str,
        translation: str = "",
        example: str = "",
        language: str = "en",
        increment: bool = True,
    ) -> Optional[Dict[str, Any]]:
        word = _clean(word, 80)
        translation = _clean(translation, 120)
        example = _clean(example, MAX_EXAMPLE_CHARS)
        if not word or not _is_latin(word):
            return None
        language = "en" if str(language).lower().startswith("en") else "es"

        with self.connect() as db:
            # ON CONFLICT upsert (tutor_memory style)
            if increment:
                db.execute(
                    """INSERT INTO vocab
                           (word, translation, example, language, times_seen, next_review, created_at)
                       VALUES (?, ?, ?, ?, 1, ?, datetime('now'))
                       ON CONFLICT(word, language) DO UPDATE SET
                           times_seen = times_seen + 1,
                           translation = CASE WHEN ?<>'' THEN ? ELSE translation END,
                           example = CASE WHEN ?<>'' THEN ? ELSE example END,
                           updated_at = datetime('now')""",
                    (word, translation, example, language, _days_from_now(1),
                     translation, translation, example, example),
                )
            else:
                db.execute(
                    """INSERT INTO vocab
                           (word, translation, example, language, times_seen, next_review, created_at)
                       VALUES (?, ?, ?, ?, 1, ?, datetime('now'))
                       ON CONFLICT(word, language) DO UPDATE SET
                           translation = CASE WHEN translation='' THEN ? ELSE translation END,
                           example = CASE WHEN example='' THEN ? ELSE example END,
                           updated_at = datetime('now')""",
                    (word, translation, example, language, _days_from_now(1),
                     translation, example),
                )
            row = db.execute(
                "SELECT * FROM vocab WHERE word=? AND language=?", (word, language)
            ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def _schedule(interval: int, ease: float, quality: int) -> Tuple[int, float, str]:
        """SM-2 simplificado (estilo tutor_memory): acierto alarga, fallo reinicia."""
        interval = max(1, int(interval or 1))
        ease = max(1.3, float(ease or 2.5))
        if quality < 3:  # fallo
            interval = 1
            ease = max(1.3, ease - 0.2)
            failed_delta = 1
        else:  # acierto
            if interval <= 1:
                interval = 1
            interval = round(interval * ease)
            ease = min(2.8, ease + 0.05)
            failed_delta = 0
        return interval, round(ease, 2), _days_from_now(interval), failed_delta

    def review_item(self, kind: str, item_id: int, quality: int) -> bool:
        """Registra repaso (0-5): <3 = fallo, >=3 = acierto. Actualiza SRS."""
        quality = max(0, min(5, int(quality)))
        table = "vocab" if kind == "vocab" else "errors"
        ok_col = "times_ok"
        fail_col = "times_failed"
        with self.connect() as db:
            row = db.execute(f"SELECT * FROM {table} WHERE id=?", (int(item_id),)).fetchone()
            if not row:
                return False
            interval, ease, next_review, failed_delta = self._schedule(
                row["interval"], row["ease"], quality
            )
            db.execute(
                f"""UPDATE {table} SET
                        interval=?, ease=?, next_review=?,
                        {ok_col}={ok_col}+1,
                        {fail_col}={fail_col}+?,
                        updated_at=datetime('now')
                    WHERE id=?""",
                (interval, ease, next_review, failed_delta, int(item_id)),
            )
        return True

    def record_review(self, item_id: int, kind: str, correct: bool) -> Dict[str, Any]:
        """API simple para tool calling: correct=True/False en lugar de quality 0-5."""
        quality = 5 if correct else 0
        ok = self.review_item(kind, int(item_id), quality)
        next_review = ""
        if ok:
            with self.connect() as db:
                table = "vocab" if kind == "vocab" else "errors"
                row = db.execute(f"SELECT next_review FROM {table} WHERE id=?", (int(item_id),)).fetchone()
                if row:
                    next_review = row["next_review"]
        return {"ok": ok, "next_review": next_review}

    def get_due_reviews(self, limit: int = 5) -> List[Dict[str, Any]]:
        limit = max(1, min(20, int(limit)))
        rows: List[Dict[str, Any]] = []
        with self.connect() as db:
            errors = db.execute(
                """SELECT id, item, corrected, explanation, example, kind,
                          times_failed, interval
                   FROM errors
                   WHERE date(next_review) <= date('now')
                   ORDER BY times_failed DESC, next_review ASC
                   LIMIT ?""",
                (limit,),
            ).fetchall()
            for row in errors:
                rows.append({
                    "kind": "error",
                    "id": row["id"],
                    "front": row["item"],
                    "back": row["corrected"],
                    "extra": row["explanation"] or row["example"],
                    "times_failed": row["times_failed"],
                })
            remaining = limit - len(rows)
            if remaining > 0:
                vocab = db.execute(
                    """SELECT id, word, translation, example, times_failed, interval
                       FROM vocab
                       WHERE date(next_review) <= date('now')
                       ORDER BY times_failed DESC, next_review ASC
                       LIMIT ?""",
                    (remaining,),
                ).fetchall()
                for row in vocab:
                    rows.append({
                        "kind": "vocab",
                        "id": row["id"],
                        "front": row["word"],
                        "back": row["translation"],
                        "extra": row["example"],
                        "times_failed": row["times_failed"],
                    })
        return rows

    # -- sesiones / turnos --------------------------------------------------

    def start_session(self) -> int:
        with self.connect() as db:
            cursor = db.execute("INSERT INTO sessions DEFAULT VALUES")
            return int(cursor.lastrowid)

    def end_session(self, session_id: int) -> None:
        if not session_id:
            return
        with self.connect() as db:
            db.execute(
                "UPDATE sessions SET ended_at=datetime('now') WHERE id=? AND ended_at IS NULL",
                (int(session_id),),
            )

    def log_turn(
        self,
        session_id: int,
        user_text: str,
        assistant_text: str,
        language: str = "es",
        corrections: Optional[List[Dict[str, Any]]] = None,
        vocabulary: Optional[List[Dict[str, Any]]] = None,
        turn: int = 0,
    ) -> Dict[str, int]:
        corrections = corrections or []
        vocabulary = vocabulary or []
        language = "en" if str(language).lower().startswith("en") else "es"
        saved_errors = 0
        saved_vocab = 0
        correction_terms: set = set()

        with self.connect() as db:
            if not turn:
                row = db.execute(
                    "SELECT COALESCE(MAX(turn), 0) AS n FROM turns WHERE session_id=?",
                    (int(session_id),),
                ).fetchone()
                turn = int(row["n"]) + 1
            cursor = db.execute(
                """INSERT INTO turns
                   (session_id, turn, user_text, assistant_text, language)
                   VALUES (?, ?, ?, ?, ?)""",
                (int(session_id), turn, str(user_text or "")[:4000],
                 str(assistant_text or "")[:4000], language),
            )
            db.execute(
                "INSERT INTO turns_fts(rowid, user_text, assistant_text) VALUES (?, ?, ?)",
                (cursor.lastrowid, str(user_text or ""), str(assistant_text or "")),
            )

        for correction in corrections:
            if not isinstance(correction, dict):
                continue
            original = _clean(correction.get("original"))
            corrected = _clean(correction.get("corrected"))
            if not original and not corrected:
                continue
            if not _shares_words(original, user_text):
                continue
            saved = self.save_error(
                original,
                corrected,
                explanation=str(correction.get("explanation") or ""),
                kind=str(correction.get("type") or "grammar"),
                language=language,
            )
            if saved:
                saved_errors += 1
                correction_terms.add(_norm(original))
                correction_terms.add(_norm(corrected))

        for entry in vocabulary:
            if isinstance(entry, str):
                word, translation, example = entry, "", ""
            elif isinstance(entry, dict):
                word = entry.get("word") or entry.get("term") or ""
                translation = entry.get("translation") or entry.get("meaning") or ""
                example = entry.get("example") or ""
            else:
                continue
            if _norm(word) in correction_terms:
                continue
            saved = self.save_vocab(
                word, translation, example, language=language
            )
            if saved:
                saved_vocab += 1

        with self.connect() as db:
            db.execute(
                """UPDATE sessions SET
                       turns=turns+1,
                       corrections=corrections+?,
                       vocab_added=vocab_added+?
                   WHERE id=?""",
                (saved_errors, saved_vocab, int(session_id)),
            )
        return {"errors": saved_errors, "vocab": saved_vocab, "turn": turn}

    # -- busqueda -----------------------------------------------------------

    @staticmethod
    def _fts_query(text: str) -> str:
        tokens = [
            token for token in _WORD_RE.findall(_norm(text))
            if len(token) >= 3
        ]
        return " OR ".join(f'"{token}"' for token in tokens[:8])

    def search_sessions(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Busca en turnos (turns_fts) y resumenes de sesiones (sessions_fts)."""
        limit = max(1, min(10, int(limit)))
        match = self._fts_query(query)
        if not match:
            return []
        results: List[Dict[str, Any]] = []
        seen = set()
        with self.connect() as db:
            # 1) Buscar en turnos (detalle de la conversacion)
            try:
                rows = db.execute(
                    """SELECT t.user_text, t.assistant_text, t.created_at,
                              s.started_at, bm25(turns_fts) AS score
                         FROM turns_fts
                         JOIN turns t ON t.id = turns_fts.rowid
                         JOIN sessions s ON s.id = t.session_id
                         WHERE turns_fts MATCH ?
                         ORDER BY score ASC
                         LIMIT ?""",
                    (match, limit),
                ).fetchall()
            except sqlite3.OperationalError:
                rows = []
            for row in rows:
                key = (_norm(row["user_text"])[:80], _norm(row["assistant_text"])[:80])
                if key in seen:
                    continue
                seen.add(key)
                results.append({
                    "user_text": str(row["user_text"])[:300],
                    "assistant_text": str(row["assistant_text"])[:300],
                    "date": str(row["started_at"] or row["created_at"] or "")[:10],
                })
                if len(results) >= limit:
                    return results

            # 2) Buscar en resumenes de sesiones (sessions_fts) si faltan resultados
            if len(results) < limit:
                try:
                    rows2 = db.execute(
                        """SELECT s.started_at, s.summary, s.topics, bm25(sessions_fts) AS score
                           FROM sessions_fts
                           JOIN sessions s ON s.id = sessions_fts.rowid
                           WHERE sessions_fts MATCH ?
                           ORDER BY score ASC
                           LIMIT ?""",
                        (match, limit - len(results)),
                    ).fetchall()
                except sqlite3.OperationalError:
                    rows2 = []
                for row in rows2:
                    key = (_norm(row["summary"])[:80],)
                    if key in seen:
                        continue
                    seen.add(key)
                    results.append({
                        "user_text": "",
                        "assistant_text": str(row["summary"])[:300],
                        "date": str(row["started_at"] or "")[:10],
                    })
                    if len(results) >= limit:
                        break

            # 3) Fallback LIKE si FTS falla
            if not results:
                for token in match.replace('"', "").split(" OR "):
                    pattern = f"%{token}%"
                    rows3 = db.execute(
                        """SELECT user_text, assistant_text, created_at,
                                  started_at, 0 AS score
                             FROM turns
                             WHERE user_text LIKE ? OR assistant_text LIKE ?
                             ORDER BY id DESC LIMIT ?""",
                        (pattern, pattern, limit),
                    ).fetchall()
                    for row in rows3:
                        key = (_norm(row["user_text"])[:80], _norm(row["assistant_text"])[:80])
                        if key in seen:
                            continue
                        seen.add(key)
                        results.append({
                            "user_text": str(row["user_text"])[:300],
                            "assistant_text": str(row["assistant_text"])[:300],
                            "date": str(row["started_at"] or row["created_at"] or "")[:10],
                        })
                        if len(results) >= limit:
                            break
                    if len(results) >= limit:
                        break
        return results

    # -- consolidacion ------------------------------------------------------

    def _session_turns(self, session_id: int, limit: int = 60) -> List[Dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute(
                """SELECT turn, user_text, assistant_text, language
                   FROM turns WHERE session_id=? ORDER BY turn ASC LIMIT ?""",
                (int(session_id), int(limit)),
            ).fetchall()
        return [dict(row) for row in rows]

    def consolidate_session(
        self,
        session_id: int,
        model: str,
        url: str = "http://localhost:11434",
        num_ctx: int = 8192,
        timeout: int = 120,
    ) -> Dict[str, Any]:
        """Extrae errores, vocabulario y resumen con una llamada JSON final.

        El JSON se valida, se deduplica y se aplica aqui; si el modelo devuelve
        algo mal formado se reintenta una sola vez.
        """
        turns = self._session_turns(session_id)
        if len(turns) < 2:
            self.end_session(session_id)
            return {"skipped": True, "reason": "few_turns"}

        transcript_parts: List[str] = []
        for turn in turns:
            transcript_parts.append(f"U: {turn['user_text']}")
            transcript_parts.append(f"E: {turn['assistant_text']}")
        transcript = "\n".join(transcript_parts)
        if len(transcript) > MAX_TRANSCRIPT_CHARS:
            transcript = transcript[-MAX_TRANSCRIPT_CHARS:]

        schema = {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "topics": {"type": "array", "items": {"type": "string"}},
                "interests": {"type": "array", "items": {"type": "string"}},
                "level_estimate": {"type": "string", "enum": list(LEVELS)},
                "errors": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "item": {"type": "string"},
                            "corrected": {"type": "string"},
                            "explanation": {"type": "string"},
                            "example": {"type": "string"},
                        },
                        "required": ["item", "corrected"],
                    },
                },
                "vocabulary": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "word": {"type": "string"},
                            "translation": {"type": "string"},
                            "example": {"type": "string"},
                        },
                        "required": ["word", "translation"],
                    },
                },
            },
            "required": ["summary", "errors", "vocabulary"],
        }

        system = (
            "Eres un extractor de datos de una sesion de clase de idiomas. "
            "Devuelve SOLO JSON valido. No inventes: usa unicamente lo que "
            "aparece en la transcripcion. En 'errors' incluye errores reales "
            "del alumno con la forma dicha (item) y la forma correcta "
            "(corrected). En 'vocabulary' incluye palabras o expresiones "
            "nuevas que se explicaron. 'summary' en una o dos frases. "
            "'interests' son temas que al alumno le gustan. 'level_estimate' "
            "solo si hay evidencia suficiente; si no, dejalo vacio."
        )
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": "Transcripcion:\n" + transcript},
        ]

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "think": False,
            "format": schema,
            "keep_alive": "10m",
            "options": {
                "temperature": 0.2,
                "top_p": 0.9,
                "repeat_penalty": 1.05,
                "num_predict": 900,
                "num_ctx": int(num_ctx),
            },
        }

        data: Optional[Dict[str, Any]] = None
        raw = ""
        for attempt in range(2):
            try:
                body = json.dumps(payload).encode("utf-8")
                request = urllib.request.Request(
                    url.rstrip("/") + "/api/chat",
                    data=body,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    result = json.load(response)
                raw = str(result.get("message", {}).get("content") or "")
                data = json.loads(raw)
                if isinstance(data, dict):
                    break
            except Exception as exc:
                print(f"[MEM] Consolidacion intento {attempt + 1} fallido: {exc}")
                data = None
                if attempt == 0:
                    messages.append({
                        "role": "user",
                        "content": "El JSON anterior no era valido. Devuelve solo el objeto JSON.",
                    })

        if not isinstance(data, dict):
            self.end_session(session_id)
            return {"skipped": True, "reason": "bad_json", "raw": raw[:200]}

        summary = _clean(data.get("summary"), MAX_SUMMARY_CHARS)
        topics = [
            _clean(item, 60) for item in (data.get("topics") or [])
            if isinstance(item, str) and _clean(item, 60)
        ][:8]
        errors = data.get("errors") if isinstance(data.get("errors"), list) else []
        vocab = data.get("vocabulary") if isinstance(data.get("vocabulary"), list) else []

        applied_errors = 0
        applied_vocab = 0
        error_terms: set = set()
        for entry in errors[:25]:
            if not isinstance(entry, dict):
                continue
            saved = self.save_error(
                entry.get("item") or "",
                entry.get("corrected") or "",
                explanation=str(entry.get("explanation") or ""),
                example=str(entry.get("example") or ""),
                increment=False,
            )
            if saved:
                applied_errors += 1
                error_terms.add(_norm(saved.get("item") or ""))
                error_terms.add(_norm(saved.get("corrected") or ""))

        for entry in vocab[:25]:
            if not isinstance(entry, dict):
                continue
            word = entry.get("word") or ""
            if _norm(word) in error_terms:
                continue
            saved = self.save_vocab(
                word,
                entry.get("translation") or "",
                entry.get("example") or "",
                language="en",
                increment=False,
            )
            if saved:
                applied_vocab += 1

        interests = [
            item for item in (data.get("interests") or [])
            if isinstance(item, str)
        ]
        if interests:
            self.merge_interests(interests)

        level = str(data.get("level_estimate") or "").upper()
        if level in LEVELS:
            self.set_profile_value("level", level)

        if summary:
            self.set_profile_value("last_summary", summary)

        with self.connect() as db:
            db.execute(
                """UPDATE sessions SET summary=?, topics=?, ended_at=datetime('now')
                   WHERE id=?""",
                (summary, ", ".join(topics), int(session_id)),
            )

        return {
            "skipped": False,
            "summary": summary,
            "topics": topics,
            "errors_saved": applied_errors,
            "vocab_saved": applied_vocab,
            "interests": interests[:8],
            "level": level if level in LEVELS else "",
        }

    # -- migracion ----------------------------------------------------------

    def migrate_legacy(
        self,
        memory_path: str = LEGACY_MEMORY,
        learning_path: str = LEGACY_LEARNING,
        import_errors: bool = False,
    ) -> Dict[str, int]:
        with self.connect() as db:
            if db.execute(
                "SELECT 1 FROM migrations WHERE name='legacy_json_v1'"
            ).fetchone():
                return {"imported_turns": 0, "imported_errors": 0, "already": 1}

        imported_turns = 0
        imported_errors = 0

        records: List[Dict[str, Any]] = []
        try:
            with open(memory_path, "r", encoding="utf-8") as handle:
                loaded = json.load(handle)
            if isinstance(loaded, list):
                records = [item for item in loaded if isinstance(item, dict)]
        except Exception as exc:
            print(f"[MEM] Sin memoria JSON que migrar: {exc}")

        if records:
            session_id = self.start_session()
            for index, item in enumerate(records, start=1):
                user_text = str(item.get("usuario") or "")
                assistant_text = str(item.get("asistente") or "")
                if not user_text and not assistant_text:
                    continue
                self.log_turn(
                    session_id,
                    user_text,
                    assistant_text,
                    language=str(item.get("idioma_usuario") or "es"),
                    corrections=[],
                    vocabulary=[],
                    turn=index,
                )
                imported_turns += 1
            self.end_session(session_id)

        # Correcciones historicas del perfil JSON antiguo. Por defecto NO se
        # importan: el perfil viejo mezclaba traducciones y frases de broma.
        if import_errors:
            try:
                with open(learning_path, "r", encoding="utf-8") as handle:
                    learning = json.load(handle)
                if isinstance(learning, dict):
                    for entry in (learning.get("recent_corrections") or [])[:40]:
                        if not isinstance(entry, dict):
                            continue
                        if self.save_error(
                            entry.get("original") or "",
                            entry.get("corrected") or "",
                            explanation=str(entry.get("explanation") or ""),
                            kind=str(entry.get("type") or "grammar"),
                            increment=False,
                        ):
                            imported_errors += 1
                    for pattern, count in (learning.get("by_pattern") or {}).items():
                        if "->" not in str(pattern):
                            continue
                        original, corrected = str(pattern).split("->", 1)
                        saved = self.save_error(
                            original.strip(), corrected.strip(), increment=False
                        )
                        if saved:
                            with self.connect() as db:
                                db.execute(
                                    "UPDATE errors SET times_failed=? WHERE id=?",
                                    (max(1, int(count or 1)), saved["id"]),
                                )
                            imported_errors += 1
            except Exception as exc:
                print(f"[MEM] Sin perfil JSON que migrar: {exc}")

        # Los repasos historicos quedan disponibles desde la primera sesion.
        with self.connect() as db:
            db.execute("UPDATE errors SET next_review=date('now')")
            db.execute("UPDATE vocab SET next_review=date('now')")

        with self.connect() as db:
            db.execute("INSERT INTO migrations(name) VALUES ('legacy_json_v1')")
        return {
            "imported_turns": imported_turns,
            "imported_errors": imported_errors,
            "already": 0,
        }


# ---------------------------------------------------------------------------
# Instancia global
# ---------------------------------------------------------------------------

_STORE: Optional[MemoryStore] = None


def get_store(db_path: Optional[str] = None) -> MemoryStore:
    global _STORE
    if _STORE is None or (db_path and str(_STORE.db_path) != str(db_path)):
        _STORE = MemoryStore(db_path or DB_PATH)
    return _STORE


def get_user_name() -> str:
    """Nombre del usuario desde SQLite (fuente unica)."""
    return get_store().get_user_name()


def set_user_name(name: Any) -> str:
    """Guarda el nombre en SQLite y devuelve el valor normalizado."""
    return get_store().set_user_name(name)


def clear_user_name() -> None:
    """Borra el nombre del perfil SQLite."""
    get_store().clear_user_name()


def log_turn(
    session_id: int,
    user_text: str,
    assistant_text: str,
    language: str = "es",
    corrections: Optional[List[Dict[str, Any]]] = None,
    vocabulary: Optional[List[Dict[str, Any]]] = None,
    turn: int = 0,
) -> Dict[str, int]:
    """Guarda un turno en la sesion abierta (envoltorio de MemoryStore.log_turn)."""
    return get_store().log_turn(
        session_id,
        user_text,
        assistant_text,
        language,
        corrections=corrections,
        vocabulary=vocabulary,
        turn=turn,
    )


def consolidate_session(
    session_id: int,
    model: str,
    url: str = "http://localhost:11434",
    num_ctx: int = 8192,
    timeout: int = 120,
) -> Dict[str, Any]:
    """Consolida la sesion (envoltorio de MemoryStore.consolidate_session)."""
    return get_store().consolidate_session(
        session_id, model, url, num_ctx, timeout
    )


# ---------------------------------------------------------------------------
# Bloques para el prompt (perfil pequeno, nunca historial largo)
# ---------------------------------------------------------------------------

def build_profile_block(max_chars: int = MAX_PROFILE_CHARS) -> str:
    store = get_store()
    profile = store.get_profile()
    lines: List[str] = []

    if profile.get("level"):
        lines.append(f"- Nivel MCER: {profile['level']}")
    if profile.get("native_language") or profile.get("target_language"):
        lines.append(
            f"- Idiomas: nativo {profile.get('native_language') or '?'} / "
            f"objetivo {profile.get('target_language') or '?'}"
        )
    if profile.get("goals"):
        lines.append(f"- Objetivos: {profile['goals']}")
    if profile.get("interests"):
        lines.append(f"- Intereses: {profile['interests']}")

    with store.connect() as db:
        frequent = db.execute(
            """SELECT item, corrected, times_failed FROM errors
               WHERE times_failed >= 2
               ORDER BY times_failed DESC, updated_at DESC LIMIT 4"""
        ).fetchall()
        due = db.execute(
            "SELECT COUNT(*) AS n FROM errors WHERE date(next_review) <= date('now')"
        ).fetchone()["n"]
        due_vocab = db.execute(
            "SELECT COUNT(*) AS n FROM vocab WHERE date(next_review) <= date('now')"
        ).fetchone()["n"]

    if frequent:
        samples = []
        for row in frequent:
            text = f"{row['item']} -> {row['corrected']}" if row["corrected"] else row["item"]
            samples.append(f"{text} (x{row['times_failed']})")
        lines.append("- Errores frecuentes: " + "; ".join(samples))

    due_total = int(due or 0) + int(due_vocab or 0)
    if due_total:
        lines.append(f"- Repasos pendientes: {due_total}")

    if not lines:
        return ""
    block = "PERFIL DEL ALUMNO (memoria real, no inventes nada mas):\n" + "\n".join(lines)
    if len(block) > max_chars:
        block = block[: max_chars - 3].rstrip() + "..."
    return block


def build_due_block(limit: int = 3, language: str = "es") -> str:
    items = get_store().get_due_reviews(limit)
    if not items:
        return ""
    if str(language).lower().startswith("en"):
        lines = ["REVIEWS DUE THIS SESSION (ask the user if they want to do them now):"]
        for item in items:
            back = f" -> {item['back']}" if item.get("back") else ""
            lines.append(f"- {item['front']}{back}")
    else:
        lines = ["REPASOS PENDIENTES (pregunta al usuario si quiere hacerlos ahora):"]
        for item in items:
            back = f" -> {item['back']}" if item.get("back") else ""
            lines.append(f"- {item['front']}{back}")
    return "\n".join(lines)


def build_prompt_block(
    include_due: bool = False,
    language: str = "es",
    max_chars: int = MAX_PROFILE_CHARS,
) -> str:
    parts = [build_profile_block(max_chars=max_chars)]
    if include_due:
        due = build_due_block(language=language)
        if due:
            parts.append(due)
    return "\n\n".join(part for part in parts if part)


def search_memories(query: str, limit: int = 2) -> List[str]:
    """Lineas compactas para el prompt, solo si vienen al caso."""
    results = get_store().search_sessions(query, limit=limit)
    lines = []
    for item in results:
        user_text = " ".join(str(item.get("user_text") or "").split())[:140]
        assistant_text = " ".join(str(item.get("assistant_text") or "").split())[:140]
        if not user_text:
            continue
        lines.append(
            f'- ({item.get("date") or "?"}) El usuario dijo: "{user_text}"\n'
            f'  Emma respondio: "{assistant_text}"'
        )
    return lines


# ---------------------------------------------------------------------------
# Hechos declarados por el usuario (nivel, objetivos)
# ---------------------------------------------------------------------------

_LEVEL_RE = re.compile(
    r"\b(?:mi nivel es|my level is|i(?:'m| am)|soy)\s+(A1|A2|B1|B2|C1|C2)\b",
    re.IGNORECASE,
)
_GOAL_RE = re.compile(
    r"\b(?:mi objetivo es|my goal is|"
    r"quiero aprender (?:ingl[eé]s|espa[nñ]ol) para|"
    r"i want to learn (?:english|spanish) (?:to|for))\s+(.{3,200})",
    re.IGNORECASE,
)


def remember_user_facts(text: str) -> Dict[str, str]:
    """Guarda nivel MCER u objetivo si el usuario los declara explicitamente."""
    raw = str(text or "")
    changes: Dict[str, str] = {}
    if not raw.strip():
        return changes

    match = _LEVEL_RE.search(raw)
    if match:
        level = match.group(1).upper()
        if get_store().get_profile().get("level") != level:
            get_store().set_profile_value("level", level)
            changes["level"] = level

    match = _GOAL_RE.search(raw)
    if match:
        goal = _clean(match.group(1), 300)
        if goal and _is_latin(goal):
            get_store().set_profile_value("goals", goal)
            changes["goals"] = goal
    return changes


# ---------------------------------------------------------------------------
# Herramientas de memoria (5, con descripciones cortas)
# ---------------------------------------------------------------------------

MEMORY_TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_profile",
            "description": "Perfil del alumno: nivel, objetivos, intereses y errores frecuentes.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_error",
            "description": "Guarda un error del alumno para repasarlo con SRS.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item": {"type": "string", "description": "Lo que dijo el alumno."},
                    "corrected": {"type": "string", "description": "Forma correcta."},
                    "explanation": {"type": "string", "description": "Explicacion breve."},
                    "example": {"type": "string", "description": "Ejemplo de uso."},
                },
                "required": ["item", "corrected"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_vocab",
            "description": "Guarda vocabulario nuevo para repasarlo con SRS.",
            "parameters": {
                "type": "object",
                "properties": {
                    "word": {"type": "string", "description": "Palabra o expresion."},
                    "translation": {"type": "string", "description": "Traduccion."},
                    "example": {"type": "string", "description": "Ejemplo de uso."},
                },
                "required": ["word", "translation"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_due_reviews",
            "description": "Repasos que tocan hoy (errores y vocabulario).",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Maximo 1-10."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_sessions",
            "description": "Busca en conversaciones anteriores por palabras clave.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Palabras clave."},
                    "limit": {"type": "integer", "description": "Maximo 1-5."},
                },
                "required": ["query"],
            },
        },
    },
]


class ToolArgumentError(ValueError):
    pass


def _arg_str(args: Dict[str, Any], key: str, required: bool = True, max_len: int = 200) -> str:
    value = args.get(key)
    if value is None:
        if required:
            raise ToolArgumentError(f"Falta el argumento '{key}'")
        return ""
    if not isinstance(value, (str, int, float)):
        raise ToolArgumentError(f"'{key}' debe ser texto")
    text = _clean(value, max_len)
    if required and not text:
        raise ToolArgumentError(f"'{key}' no puede estar vacio")
    return text


def _arg_int(args: Dict[str, Any], key: str, default: int, low: int, high: int) -> int:
    value = args.get(key, default)
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ToolArgumentError(f"'{key}' debe ser un entero")
    return max(low, min(high, number))


def execute_tool(name: str, args: Any) -> Dict[str, Any]:
    """Valida los argumentos y ejecuta una herramienta. Nunca lanza por args."""
    if isinstance(args, str):
        try:
            args = json.loads(args or "{}")
        except json.JSONDecodeError:
            return {"ok": False, "error": "argumentos no son JSON valido"}
    if not isinstance(args, dict):
        return {"ok": False, "error": "argumentos deben ser un objeto JSON"}

    store = get_store()
    try:
        if name == "get_profile":
            return {"ok": True, "result": store.get_profile()}

        if name == "save_error":
            item = _arg_str(args, "item")
            corrected = _arg_str(args, "corrected")
            saved = store.save_error(
                item,
                corrected,
                explanation=_arg_str(args, "explanation", required=False),
                example=_arg_str(args, "example", required=False),
            )
            return {"ok": bool(saved), "result": saved}

        if name == "save_vocab":
            word = _arg_str(args, "word", max_len=80)
            translation = _arg_str(args, "translation", max_len=120)
            saved = store.save_vocab(
                word, translation,
                example=_arg_str(args, "example", required=False),
            )
            return {"ok": bool(saved), "result": saved}

        if name == "get_due_reviews":
            limit = _arg_int(args, "limit", 5, 1, 10)
            return {"ok": True, "result": store.get_due_reviews(limit)}

        if name == "search_sessions":
            query = _arg_str(args, "query", max_len=200)
            limit = _arg_int(args, "limit", 3, 1, 5)
            return {"ok": True, "result": store.search_sessions(query, limit)}

        if name == "record_review":
            item_id = _arg_int(args, "item_id", 0, 1, 9999)
            kind = _arg_str(args, "kind")
            if kind not in ("error", "vocab"):
                return {"ok": False, "error": "kind debe ser 'error' o 'vocab'"}
            correct = args.get("correct")
            if not isinstance(correct, bool):
                return {"ok": False, "error": "correct debe ser boolean"}
            return store.record_review(item_id, kind, correct)

        return {"ok": False, "error": f"herramienta desconocida: {name}"}
    except ToolArgumentError as exc:
        return {"ok": False, "error": str(exc), "retry": True}
    except Exception as exc:
        return {"ok": False, "error": f"fallo interno: {exc}"}


# ---------------------------------------------------------------------------
# Intenciones de memoria (respuesta directa, sin pasar por el LLM)
# ---------------------------------------------------------------------------

_DUE_RE = re.compile(
    r"\b(que (tengo|hay) que repasar|que toca repasar|repasos? pendientes?|"
    r"que reviso|repasemos|what (should|do) i review|what'?s due|"
    r"what do i have to review|reviews? due)\b",
    re.IGNORECASE,
)
_PROFILE_RE = re.compile(
    r"\b(que sabes de mi|que recuerdas de mi|mi perfil|como voy|"
    r"mi progreso|what do you know about me|my profile|my progress)\b",
    re.IGNORECASE,
)
_SEARCH_RE = re.compile(
    r"(?:\bque\b|\bde que\b|\bsobre que\b)\s+(?:hablamos|hemos hablado|dijimos|"
    r"comentamos)\s+(?:de|sobre)?\s*(.+)$"
    r"|(?:recuerdas|te acuerdas|te acordas)\s+(?:lo que|cuando|de cuando|de lo que)?\s*"
    r"(?:hablamos|hemos hablado|hablabamos|dijimos|te dije|comentamos)\s*"
    r"(?:de|sobre)?\s*(.+)$"
    r"|(?:recuerdas|te acuerdas)\s+(?:mi|el|la|lo de|de)\s+(.+)$"
    r"|do you remember\s+(?:what|when)\s+(?:we|i)\s+(?:talked|spoke|said|told you)\s*"
    r"(?:about|of)?\s*(.+)$"
    r"|what did\s+(?:we|i)\s+(?:talk|say)\s+about\s*(.+)$"
    r"|\bsearch (?:our )?(?:conversations?|sessions?) (?:about|for)\s+(.+)$",
    re.IGNORECASE,
)


def detect_memory_intent(text: str) -> Optional[Dict[str, Any]]:
    raw = str(text or "").strip()
    if not raw:
        return None
    # Se compara sin tildes ("qué" -> "que") para que el reconocimiento sea
    # igual de fiable por voz que por texto.
    normalized = _norm(raw)
    match = _SEARCH_RE.search(normalized)
    if match:
        query = next((group for group in match.groups() if group), "")
        query = _clean(query, 120).strip(" ?!.,")
        query = re.sub(r"^(de|del|sobre|about|regarding|of)\s+", "", query)
        if query:
            return {"name": "search_sessions", "args": {"query": query}}
        return None
    if _DUE_RE.search(normalized):
        return {"name": "get_due_reviews", "args": {"limit": 3}}
    if _PROFILE_RE.search(normalized):
        return {"name": "get_profile", "args": {}}
    return None


def answer_intent(intent: Dict[str, Any], language: str = "es") -> Optional[str]:
    """Convierte el resultado de una herramienta en una respuesta hablada."""
    name = intent.get("name")
    result = execute_tool(name, intent.get("args") or {})
    if not result.get("ok"):
        return None
    data = result.get("result")
    english = str(language).lower().startswith("en")

    if name == "get_due_reviews":
        items = data or []
        if not items:
            return "You have no reviews due. Want to practise something else?" if english else "No tienes repasos pendientes. ¿Practicamos otra cosa?"
        if english:
            first = items[0]
            back = f" It means '{first['back']}'." if first.get("back") else ""
            return (
                f"You have {len(items)} reviews due. Let's start: "
                f"do you remember '{first['front']}'?{back}"
            )
        first = items[0]
        back = f" Significa '{first['back']}'." if first.get("back") else ""
        return (
            f"Tienes {len(items)} repasos pendientes. Empecemos: "
            f"¿recuerdas «{first['front']}»?{back}"
        )

    if name == "get_profile":
        profile = data or {}
        parts_es = []
        parts_en = []
        if profile.get("level"):
            parts_es.append(f"nivel {profile['level']}")
            parts_en.append(f"level {profile['level']}")
        if profile.get("goals"):
            parts_es.append(f"objetivos: {profile['goals']}")
            parts_en.append(f"goals: {profile['goals']}")
        if profile.get("interests"):
            parts_es.append(f"intereses: {profile['interests']}")
            parts_en.append(f"interests: {profile['interests']}")
        if not parts_es:
            return ("I don't have a profile yet. Tell me your goals and interests." if english
                    else "Todavía no tengo tu perfil. Cuéntame tus objetivos e intereses.")
        prefix = "This is what I know: " if english else "Esto es lo que sé: "
        return prefix + ("; ".join(parts_en) if english else "; ".join(parts_es)) + "."

    if name == "search_sessions":
        rows = data or []
        if not rows:
            return ("I couldn't find anything about that." if english
                    else "No he encontrado nada sobre eso.")
        row = rows[0]
        if english:
            return (
                f"On {row['date']} you said: \"{row['user_text']}\". "
                f"I answered: \"{row['assistant_text']}\"."
            )
        return (
            f"El {row['date']} dijiste: «{row['user_text']}». "
            f"Yo respondí: «{row['assistant_text']}»."
        )
    return None


# ---------------------------------------------------------------------------
# CLI / pruebas
# ---------------------------------------------------------------------------

def _selftest() -> None:
    import tempfile

    path = Path(tempfile.gettempdir()) / "emma_memory_selftest.db"
    if path.exists():
        path.unlink()
    store = MemoryStore(str(path))

    assert store.get_profile()["level"] == ""
    store.set_profile_value("level", "b1")
    assert store.get_profile()["level"] == "B1"
    assert store.set_profile_value("level", "Z9")["level"] == "B1"

    # El nombre vive en el perfil SQLite (fuente unica).
    assert store.get_user_name() == ""
    assert store.set_user_name("Henry") == "Henry"
    assert store.get_user_name() == "Henry"
    store.clear_user_name()
    assert store.get_user_name() == ""

    assert store.save_error("I go to beach", "I went to the beach", "past tense")
    assert store.save_error("I go to beach", "I went to the beach", "past tense")
    with store.connect() as db:
        row = db.execute("SELECT times_failed FROM errors").fetchone()
    assert row["times_failed"] == 2

    store.save_vocab("harbour", "puerto", "The harbour is quiet.")
    store.save_vocab("harbour", "puerto")
    # Fuerza los repasos a hoy para probar la cola sin esperar un dia.
    with store.connect() as db:
        db.execute("UPDATE errors SET next_review=date('now')")
        db.execute("UPDATE vocab SET next_review=date('now')")
    due = store.get_due_reviews(5)
    assert len(due) == 2

    # SRS: acertar aleja la revision, fallar la acerca.
    error_item = next(item for item in due if item["kind"] == "error")
    assert store.review_item("error", error_item["id"], 5)
    due_after = store.get_due_reviews(5)
    assert all(item["id"] != error_item["id"] for item in due_after if item["kind"] == "error")

    session_id = store.start_session()
    store.log_turn(
        session_id, "Me gusta el cine de ciencia ficcion", "That's great.",
        language="es",
        corrections=[{"original": "yo gusto", "corrected": "me gusta", "type": "grammar"}],
        vocabulary=[{"word": "plot twist", "translation": "giro argumental"}],
    )
    store.log_turn(session_id, "Ayer vi Dune", "Did you like it?", language="es")
    found = store.search_sessions("Dune")
    assert found and "Dune" in found[0]["user_text"]

    # execute_tool usa el store global; aqui usamos el store local directamente
    assert store.get_due_reviews(2)
    assert store.search_sessions("Dune")
    assert not store.search_sessions("")
    
    # Test record_review tool via local store
    assert store.record_review(due[0]["id"], "error", True)["ok"]

    # Consolidacion sin Ollama: debe degradar sin romper.
    store.end_session(session_id)
    path.unlink()
    print("SELFTEST OK")


if __name__ == "__main__":
    import sys

    if "--selftest" in sys.argv:
        _selftest()
    else:
        store = get_store()
        if "--migrate" in sys.argv:
            print(store.migrate_legacy(import_errors="--migrate-errors" in sys.argv))
        profile = store.get_profile()
        print("Perfil:", json.dumps(profile, ensure_ascii=False, indent=2))
        print("\nBloque para el prompt:\n")
        print(build_profile_block() or "(vacio)")
        print("\nRepasos pendientes:")
        for item in store.get_due_reviews(5):
            print(f"  [{item['kind']}] {item['front']} -> {item['back']}")
