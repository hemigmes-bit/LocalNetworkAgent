import json
from datetime import datetime, timezone

from level_progression import LevelProgression
from prompts import (
    LEVEL_DESCRIPTIONS,
    MODE_INSTRUCTIONS,
    RECAP_SYSTEM,
    TUTOR_SYSTEM,
)
from providers import chat, parse_json


class Tutor:
    def __init__(self, store, client, cfg, session_id):
        self.store = store
        self.client = client
        self.cfg = cfg
        self.session_id = session_id
        learner = store.learner()
        self.student_name = learner["name"]
        self.native_language = learner["native_language"]
        self.mode = "free"
        self.scenario = ""
        self.history = []
        self.llm_history = []
        self.last_topic = None
        self.progression = LevelProgression(store.path) if cfg.get("level_progression", True) else None
        self._maybe_init_curriculum()

    def _maybe_init_curriculum(self):
        if not self.progression:
            return
        level = self.store.learner()["level"]
        for item in self.progression.get_all_items(self.store.learner()["level"]):
            with self.store.conn as c:
                c.execute("""
                    INSERT OR IGNORE INTO curriculum_progress (level, category, item, mastery, practice_count, last_practiced, created_at)
                    VALUES (?, ?, ?, 0.0, 0, ?, ?)
                """, (item["level"], item["category"], item["item"], datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat()))
            c.commit()

    def _system_prompt(self):
        learner = self.store.learner()
        level = learner["level"]
        mode_extra = ""
        if self.scenario:
            mode_extra = f"- Scenario / grammar point / topic for this session: {self.scenario}"
        recent = self.store.recent_error_types()
        recent_txt = "\n".join(
            f"- {e['error_type']}: {e['n']} recent occurrences" for e in recent
        ) or "- none yet"
        last = self.store.last_session_summary()
        if last:
            last_txt = f"topic: {last['topic']}\nsummary: {last['summary']}"
        else:
            last_txt = "none (first session)"
        return TUTOR_SYSTEM.format(
            student_name=self.student_name,
            level=level,
            level_description=LEVEL_DESCRIPTIONS.get(level, "intermediate"),
            native_language=self.native_language,
            mode=self.mode,
            mode_extra=mode_extra,
            recent_errors=recent_txt,
            last_session=last_txt,
            max_corrections=self.cfg["max_corrections_per_turn"],
        )

    def _generate(self, messages):
        raw = ""
        data = None
        for attempt in range(3):
            raw = chat(self.client, self.cfg, messages, json_mode=attempt < 2)
            data = parse_json(raw)
            if isinstance(data, dict) and str(data.get("reply") or "").strip():
                return data
        plain = (raw or "").strip()
        if plain and data is None:
            return {"reply": plain, "corrections": [], "new_vocabulary": []}
        raise RuntimeError("The model returned an empty reply. Please try again.")

    def turn(self, user_text):
        self.store.add_message(self.session_id, "user", user_text)
        messages = [{"role": "system", "content": self._system_prompt()}]
        messages.extend(self.llm_history[-16:])
        messages.append({"role": "user", "content": user_text})
        data = self._generate(messages)
        reply = str(data["reply"]).strip()
        if self.progression:
            self._update_progression(data)
        if self.progression and self.cfg.get("auto_level_up", True):
            self._check_level_up()
        if self.progression:
            self.progression.increment_sessions(self.store.learner()["level"])
        corrections = [
            c for c in data.get("corrections") or [] if isinstance(c, dict)
        ][: self.cfg["max_corrections_per_turn"]]
        new_vocab = [v for v in data.get("new_vocabulary") or [] if isinstance(v, dict)]
        self.last_topic = data.get("topic") or self.last_topic

        self.history.append({"role": "user", "content": user_text})
        self.history.append({"role": "assistant", "content": reply})
        self.llm_history.append({"role": "user", "content": user_text})
        self.llm_history.append(
            {
                "role": "assistant",
                "content": json.dumps(
                    {
                        "reply": reply,
                        "corrections": corrections,
                        "new_vocabulary": new_vocab,
                        "topic": self.last_topic,
                    },
                    ensure_ascii=False,
                ),
            }
        )
        self.store.add_message(self.session_id, "assistant", reply, corrections)
        if corrections:
            self.store.log_corrections(corrections)
        for v in new_vocab:
            self.store.add_vocab(v.get("word"), v.get("translation"), v.get("example"))
        return {
            "reply": reply,
            "language": str(data.get("language") or "en"),
            "corrections": corrections,
            "new_vocabulary": new_vocab,
            "topic": self.last_topic,
        }

    def _update_progression(self, data):
        if not self.progression:
            return
        level = self.store.learner()["level"]
        for c in data.get("corrections") or []:
            ctype = c.get("type", "grammar")
            self.progression.update_mastery(level, "grammar", ctype, 0.05)
        for v in data.get("new_vocabulary") or []:
            self.progression.update_mastery(level, "vocabulary", v.get("word", ""), 0.08)

    def _check_level_up(self):
        if not self.progression:
            return
        current = self.store.learner()["level"]
        next_level = self.progression.check_level_up(current)
        if next_level:
            self.progression.do_level_up(current, next_level)
            self.progression.record_assessment(current, next_level, 0.8, f"Auto level-up after mastery criteria met")
            self.store.set_level(next_level)
            self.progression = LevelProgression(self.store.db_path)

    def get_progress_summary(self):
        if not self.progression:
            return {}
        level = self.store.learner()["level"]
        return self.progression.get_status_summary(level)

    def get_recommendations(self, limit=3):
        if not self.progression:
            return []
        level = self.store.learner()["level"]
        return self.progression.get_recommendations(level, limit)

    def recap(self):
        transcript = "\n".join(
            f"{m['role'].upper()}: {m['content']}" for m in self.history
        )
        if not transcript:
            return None
        learner = self.store.learner()
        user_msg = (
            f"Student: {learner['name']}, CEFR level {learner['level']}, "
            f"native language {learner['native_language']}.\n"
            f"Session transcript:\n{transcript}"
        )
        data = parse_json(
            chat(
                self.client,
                self.cfg,
                [
                    {"role": "system", "content": RECAP_SYSTEM},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.3,
            )
        ) or {}
        summary_text = data.get("message") or ""
        self.store.end_session(self.session_id, self.last_topic, summary_text or None)
        return data
