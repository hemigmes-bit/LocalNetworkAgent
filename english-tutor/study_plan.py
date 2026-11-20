"""study_plan.py - Plan de trabajo personalizado de ingles.
Genera un plan de 4 semanas adaptado al nivel CEFR, errores recientes y vocabulario.
Guarda JSON (data/study_plan.json) y markdown legible (data/PLAN_ESTUDIO.md).
"""
import json
import os
from datetime import datetime
from pathlib import Path

from providers import chat, parse_json

BASE = Path(__file__).resolve().parent
PLAN_FILE = BASE / "data" / "study_plan.json"
MD_FILE = BASE / "data" / "PLAN_ESTUDIO.md"

SYSTEM = """You are Emma, an expert English teacher who designs personalized study plans.
Create a 4-week plan for a {level} student whose native language is {native}.
Student context:
- Sessions completed: {sessions}
- Vocabulary in flashcards: {vocab_total} (learned: {vocab_learned})
- Recurring error types: {errors}

Rules:
- Explanations and activity names in Spanish, target English content in English.
- 15-25 minutes per day, 5 days per week.
- Prioritize the recurring error types.
- Practical, motivating, measurable.

Return ONLY valid JSON with this exact shape:
{"weeks": [{"week": 1, "theme": "...", "goals": ["..."], "daily": [{"day": "Lunes", "activity": "...", "minutes": 15}], "vocab": ["..."], "milestone": "..."}]}
Exactly 4 weeks, 5 daily entries per week.
"""


def exists():
    return PLAN_FILE.exists()


def load():
    if not PLAN_FILE.exists():
        return None
    try:
        with open(PLAN_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def generate(client, cfg, store):
    level = store.learner()["level"] if store else cfg.get("level", "B1")
    native = cfg.get("native_language", "Spanish")
    sessions = store.session_count() if store else 0
    stats = store.vocab_stats() if store else {"total": 0, "learned": 0}
    errs = store.recent_error_types(8) if store else []
    err_txt = ", ".join(f"{e['error_type']} x{e['n']}" for e in errs) or "sin datos"

    prompt = (SYSTEM
              .replace("{level}", str(level))
              .replace("{native}", str(native))
              .replace("{sessions}", str(sessions))
              .replace("{vocab_total}", str(stats.get("total", 0)))
              .replace("{vocab_learned}", str(stats.get("learned", 0)))
              .replace("{errors}", err_txt))
    raw = chat(client, cfg,
               [{"role": "system", "content": prompt},
                {"role": "user", "content": "Genera mi plan de trabajo de 4 semanas."}],
               temperature=0.5, json_mode=True)
    data = parse_json(raw)
    if not data or "weeks" not in data:
        return False, "No pude generar el plan. Intentalo de nuevo."
    data["generated"] = datetime.now().isoformat(timespec="seconds")
    data["level"] = level
    PLAN_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PLAN_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    _write_markdown(data)
    return True, "Plan de 4 semanas generado: " + str(MD_FILE)


def _write_markdown(data):
    lines = ["# Plan de ingles - 4 semanas", "",
             "Generado: " + str(data.get("generated", "")), "",
             "Nivel: " + str(data.get("level", "")), ""]
    for w in data.get("weeks", []):
        lines.append("## Semana " + str(w.get("week")) + ": " + str(w.get("theme", "")))
        goals = w.get("goals") or []
        if goals:
            lines.append("**Objetivos:**")
            for g in goals:
                lines.append("- " + str(g))
        daily = w.get("daily") or []
        if daily:
            lines.append("")
            lines.append("| Dia | Actividad | Min |")
            lines.append("|---|---|---|")
            for d in daily:
                lines.append("| " + str(d.get("day", "")) + " | " +
                             str(d.get("activity", "")) + " | " + str(d.get("minutes", 15)) + " |")
        vocab = w.get("vocab") or []
        if vocab:
            lines.append("")
            lines.append("**Vocabulario:** " + ", ".join(str(v) for v in vocab))
        if w.get("milestone"):
            lines.append("")
            lines.append("**Hito:** " + str(w.get("milestone")))
        lines.append("")
    MD_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(MD_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def summary(max_chars=900):
    data = load()
    if not data:
        return "Aun no hay plan. Dime 'crea mi plan de ingles' o usa /plan new."
    lines = ["Plan de ingles (" + str(data.get("level", "")) + ", generado " +
             str(data.get("generated", ""))[:10] + "):"]
    for w in data.get("weeks", []):
        lines.append("")
        lines.append("Semana " + str(w.get("week")) + ": " + str(w.get("theme", "")))
        for d in (w.get("daily") or [])[:5]:
            lines.append("  " + str(d.get("day", "")) + ": " + str(d.get("activity", "")) +
                         " (" + str(d.get("minutes", 15)) + " min)")
        if w.get("milestone"):
            lines.append("  Hito: " + str(w.get("milestone")))
    text = "\n".join(lines)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n... (plan completo en data/PLAN_ESTUDIO.md)"
    return text
