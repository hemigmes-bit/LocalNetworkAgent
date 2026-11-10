"""Ejecutar manualmente tras hacer una copia de seguridad del JSON."""
import argparse
from memory_sqlite import ConversationStore

p = argparse.ArgumentParser()
p.add_argument("json_path", nargs="?", default="memoria_emma.json")
p.add_argument("--db", default="data/emma_memory.db")
a = p.parse_args()
store = ConversationStore(a.db)
result = store.import_json(a.json_path)
print(result)
print(f"Registros en SQLite: {store.count()}")
