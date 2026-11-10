"""Almacenamiento de conversaciones SQLite; importación JSON no destructiva."""
from __future__ import annotations
import json, sqlite3
from pathlib import Path
from typing import Iterable

class ConversationStore:
    def __init__(self, db_path="data/emma_memory.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                legacy_key TEXT UNIQUE,
                turno INTEGER, usuario TEXT, asistente TEXT,
                idioma_usuario TEXT, marcas_voz_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                legacy_json TEXT NOT NULL
            )""")
            db.execute("CREATE TABLE IF NOT EXISTS migrations (name TEXT PRIMARY KEY, completed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")

    def _connect(self):
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        return db

    def import_json(self, json_path, migration_name="memoria_emma_json_v1"):
        source = Path(json_path)
        records = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(records, list):
            raise ValueError("La memoria JSON debe ser una lista de registros")
        with self._connect() as db:
            if db.execute("SELECT 1 FROM migrations WHERE name=?", (migration_name,)).fetchone():
                return {"imported": 0, "skipped": len(records), "already_imported": True}
            for index, item in enumerate(records):
                if not isinstance(item, dict):
                    raise ValueError(f"Registro {index} no es un objeto JSON")
                legacy = json.dumps(item, ensure_ascii=False, sort_keys=True)
                # La clave usa índice + contenido para conservar duplicados exactos del histórico.
                key = f"{index}:{__import__('hashlib').sha256(legacy.encode('utf-8')).hexdigest()}"
                db.execute("""INSERT OR IGNORE INTO conversations
                    (legacy_key, turno, usuario, asistente, idioma_usuario, marcas_voz_json, legacy_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (key, item.get("turno"), item.get("usuario", ""), item.get("asistente", ""),
                     item.get("idioma_usuario"), json.dumps(item.get("marcas_voz", []), ensure_ascii=False), legacy))
            db.execute("INSERT INTO migrations(name) VALUES (?)", (migration_name,))
        return {"imported": len(records), "skipped": 0, "already_imported": False}

    def count(self):
        with self._connect() as db:
            return db.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
