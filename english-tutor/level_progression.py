import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any

CEFR_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]
LEVEL_ORDER = {level: i for i, level in enumerate(CEFR_LEVELS)}

CURRICULUM = {
    "A1": {
        "grammar": [
            "present_simple", "present_continuous", "past_simple_regular",
            "past_simple_irregular_top20", "future_with_going_to",
            "imperatives", "there_is_there_are", "basic_modals_can_need",
            "basic_prepositions_in_on_at", "basic_pronouns"
        ],
        "vocabulary": [
            "numbers_1_100", "days_months_seasons", "family_relationships",
            "daily_routine_verbs", "food_drink_basic", "clothing_basic",
            "house_rooms_furniture", "weather_basic", "colors_shapes",
            "common_adjectives_basic"
        ],
        "functions": [
            "greetings_introductions", "asking_personal_info", "describing_people",
            "telling_time", "shopping_basic", "ordering_food", "asking_directions",
            "describing_daily_routine", "likes_dislikes", "simple_suggestions"
        ],
        "pronunciation": [
            "basic_vowel_sounds", "consonant_clusters_basic", "word_stress_basic",
            "sentence_stress_basic", "intonation_questions_statements"
        ],
        "listening": [
            "understand_greetings", "understand_simple_instructions",
            "understand_basic_personal_info", "understand_numbers_prices"
        ],
        "reading": [
            "read_simple_signs", "read_short_messages", "read_basic_profiles",
            "read_simple_menus"
        ],
        "writing": [
            "write_basic_greetings", "fill_simple_forms", "write_short_messages",
            "write_simple_descriptions"
        ]
    },
    "A2": {
        "grammar": [
            "past_continuous", "present_perfect_basic", "comparatives_superlatives",
            "future_will", "modals_should_must_have_to", "gerunds_infinitives_basic",
            "quantifiers_some_any_much_many", "prepositions_place_time_movement",
            "relative_clauses_basic", "adverbs_frequency_manner"
        ],
        "vocabulary": [
            "travel_transport", "health_body_illness", "shopping_clothes_sizes",
            "work_jobs_basic", "education_school", "entertainment_media",
            "technology_basic", "feelings_emotions", "weather_detailed",
            "house_chores"
        ],
        "functions": [
            "making_plans", "describing_past_experiences", "giving_advice",
            "making_comparisons", "shopping_detailed", "at_doctor_pharmacy",
            "booking_accommodation", "describing_people_detailed", "apologizing",
            "expressing_opinions_simple"
        ],
        "pronunciation": [
            "past_ed_endings", "weak_forms_common", "linking_sounds_basic",
            "intonation_politeness", "stress_compound_nouns"
        ],
        "listening": [
            "understand_announcements", "understand_simple_conversations",
            "understand_instructions_directions", "understand_basic_news"
        ],
        "reading": [
            "read_emails_messages", "read_short_articles", "read_instructions",
            "read_advertisements"
        ],
        "writing": [
            "write_emails_basic", "write_simple_stories", "write_reviews_basic",
            "write_invitations"
        ]
    },
    "B1": {
        "grammar": [
            "present_perfect_vs_past", "past_perfect", "conditionals_0_1_2",
            "reported_speech_basic", "passive_voice_basic", "modals_deduction",
            "gerunds_infinitives_advanced", "phrasal_verbs_common",
            "relative_clauses_defining_nondefining", "wish_if_only"
        ],
        "vocabulary": [
            "work_career", "travel_holidays_detailed", "health_fitness",
            "technology_internet", "environment_nature", "media_news",
            "relationships_social", "money_banking", "culture_customs",
            "education_learning"
        ],
        "functions": [
            "expressing_opinions_justifying", "hypothetical_situations",
            "describing_problems_solutions", "negotiating_making_arrangements",
            "complaining_politely", "giving_detailed_advice", "storytelling",
            "expressing_regrets", "making_predictions", "summarizing"
        ],
        "pronunciation": [
            "sentence_stress_emphasis", "intonation_attitude", "connected_speech",
            "word_families_stress_shift", "rhythm_pacing"
        ],
        "listening": [
            "understand_interviews", "understand_podcasts_basic",
            "understand_discussions", "understand_instructions_detailed"
        ],
        "reading": [
            "read_articles_blogs", "read_reviews_opinions", "read_biographies",
            "read_instructions_manuals"
        ],
        "writing": [
            "write_formal_emails", "write_essays_basic", "write_reports_basic",
            "write_reviews_detailed"
        ]
    },
    "B2": {
        "grammar": [
            "conditionals_3_mixed", "subjunctive_wish", "passive_advanced",
            "modals_perfect", "inversion_emphasis", "cleft_sentences",
            "participle_clauses", "future_continuous_perfect",
            "modal_perfect_deduction", "ellipsis_substitution"
        ],
        "vocabulary": [
            "abstract_concepts", "idioms_collocations", "academic_vocabulary",
            "business_professional", "technical_scientific", "social_issues",
            "arts_culture", "politics_society", "science_technology",
            "psychology_behavior"
        ],
        "functions": [
            "debating_arguing", "presenting_arguments", "negotiating_complex",
            "expressing_nuance", "evaluating_proposals", "mediating",
            "facilitating_discussions", "giving_presentations", "writing_proposals",
            "critical_analysis"
        ],
        "pronunciation": [
            "fine_tuning_vowels", "advanced_intonation", "speech_rate_control",
            "emphasis_focus", "native_like_rhythm"
        ],
        "listening": [
            "understand_lectures", "understand_debates", "understand_media_native",
            "understand_accents_varieties"
        ],
        "reading": [
            "read_complex_articles", "read_academic_papers", "read_literature",
            "read_technical_docs"
        ],
        "writing": [
            "write_essays_argumentative", "write_reports_formal", "write_proposals",
            "write_creative_writing"
        ]
    },
    "C1": {
        "grammar": [
            "advanced_conditionals", "complex_passive", "discourse_markers_advanced",
            "hedging_cautious_language", "complex_subordination",
            "register_style_shifting"
        ],
        "vocabulary": [
            "specialized_terminology", "nuanced_synonyms", "literary_devices",
            "register_appropriate_vocab", "cultural_references"
        ],
        "functions": [
            "academic_discourse", "professional_negotiation", "diplomatic_language",
            "abstract_reasoning", "complex_problem_solving"
        ],
        "pronunciation": [
            "native_level_control", "style_shifting", "impromptu_speech"
        ],
        "listening": [
            "understand_any_register", "understand_implicit_meaning"
        ],
        "reading": [
            "read_complex_texts_any", "critical_reading"
        ],
        "writing": [
            "write_any_register", "academic_professional_writing"
        ]
    },
    "C2": {
        "grammar": ["full_mastery", "stylistic_variation", "creative_grammar"],
        "vocabulary": ["lexical_precision", "cultural_literary_depth", "neologisms"],
        "functions": ["native_level_discourse", "creative_expression", "mastery"],
        "pronunciation": ["complete_mastery"],
        "listening": ["complete_mastery"],
        "reading": ["complete_mastery"],
        "writing": ["complete_mastery"]
    }
}

SKILL_CATEGORIES = [
    "grammar", "vocabulary", "functions", "pronunciation",
    "listening", "reading", "writing"
]

LEVEL_UP_CRITERIA = {
    "A1": {"min_mastery_avg": 0.75, "min_sessions": 8, "min_vocab": 300, "skills_required": ["grammar", "vocabulary", "functions"]},
    "A2": {"min_mastery_avg": 0.75, "min_sessions": 10, "min_vocab": 600, "skills_required": ["grammar", "vocabulary", "functions", "pronunciation"]},
    "B1": {"min_mastery_avg": 0.70, "min_sessions": 12, "min_vocab": 1200, "skills_required": ["grammar", "vocabulary", "functions", "pronunciation", "listening"]},
    "B2": {"min_mastery_avg": 0.70, "min_sessions": 15, "min_vocab": 2500, "skills_required": ["grammar", "vocabulary", "functions", "pronunciation", "listening", "reading", "writing"]},
    "C1": {"min_mastery_avg": 0.65, "min_sessions": 20, "min_vocab": 5000, "skills_required": ["grammar", "vocabulary", "functions", "pronunciation", "listening", "reading", "writing"]},
}

class LevelProgression:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_tables()

    def _now(self):
        return datetime.now(timezone.utc).isoformat()

    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self):
        with self._conn() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS level_assessments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level_before TEXT, level_after TEXT,
                assessment_type TEXT, score REAL,
                details TEXT, created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS curriculum_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT, category TEXT, item TEXT,
                mastery REAL DEFAULT 0.0,
                practice_count INTEGER DEFAULT 0,
                last_practiced TEXT, created_at TEXT,
                UNIQUE(level, category, item)
            );
            CREATE TABLE IF NOT EXISTS level_mastery (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT, category TEXT,
                mastery_avg REAL DEFAULT 0.0,
                sessions_at_level INTEGER DEFAULT 0,
                updated_at TEXT,
                UNIQUE(level, category)
            );
            CREATE TABLE IF NOT EXISTS level_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_level TEXT, to_level TEXT,
                sessions_spent INTEGER, mastery_avg REAL,
                vocab_count INTEGER, created_at TEXT
            );
            """)

    def get_curriculum(self, level: str) -> Dict:
        return CURRICULUM.get(level, {})

    def get_all_items(self, level: str) -> List[Dict]:
        items = []
        for cat, topics in self.get_curriculum(level).items():
            for topic in topics:
                items.append({"level": level, "category": cat, "item": topic})
        return items

    def get_progress(self, level: str) -> List[Dict]:
        with self._conn() as c:
            c.row_factory = sqlite3.Row
            rows = c.execute(
                "SELECT * FROM curriculum_progress WHERE level = ? ORDER BY category, item",
                (level,)
            ).fetchall()
            return [dict(r) for r in rows]

    def update_mastery(self, level: str, category: str, item: str, delta: float = 0.1):
        with self._conn() as c:
            c.execute("""
                INSERT INTO curriculum_progress (level, category, item, mastery, practice_count, last_practiced, created_at)
                VALUES (?, ?, ?, ?, 1, ?, ?)
                ON CONFLICT(level, category, item) DO UPDATE SET
                    mastery = MIN(1.0, mastery + ?),
                    practice_count = practice_count + 1,
                    last_practiced = ?
            """, (level, category, item, delta, self._now(), self._now(), delta, self._now()))
            c.commit()
        self._recalc_category(level, category)

    def _recalc_category(self, level: str, category: str):
        with self._conn() as c:
            c.row_factory = sqlite3.Row
            rows = c.execute(
                "SELECT mastery FROM curriculum_progress WHERE level = ? AND category = ?",
                (level, category)
            ).fetchall()
            if not rows:
                return
            avg = sum(r["mastery"] for r in rows) / len(rows)
            c.execute("""
                INSERT INTO level_mastery (level, category, mastery_avg, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(level, category) DO UPDATE SET
                    mastery_avg = ?, updated_at = ?
            """, (level, category, avg, self._now(), avg, self._now()))
            c.commit()

    def get_mastery(self, level: str) -> Dict[str, float]:
        with self._conn() as c:
            c.row_factory = sqlite3.Row
            rows = c.execute(
                "SELECT category, mastery_avg FROM level_mastery WHERE level = ?",
                (level,)
            ).fetchall()
            return {r["category"]: r["mastery_avg"] for r in rows}

    def get_sessions_at_level(self, level: str) -> int:
        with self._conn() as c:
            row = c.execute(
                "SELECT COALESCE(SUM(sessions_at_level), 0) FROM level_mastery WHERE level = ?",
                (level,)
            ).fetchone()
            return row[0] if row else 0

    def increment_sessions(self, level: str):
        with self._conn() as c:
            c.execute("""
                INSERT INTO level_mastery (level, category, mastery_avg, sessions_at_level, updated_at)
                VALUES (?, 'functions', 0, 1, ?)
                ON CONFLICT(level, category) DO UPDATE SET
                    sessions_at_level = sessions_at_level + 1, updated_at = ?
            """, (level, self._now(), self._now()))
            c.commit()

    def get_vocab_count(self) -> int:
        with self._conn() as c:
            from db import Store
            store = Store(self.db_path)
            return store.vocab_stats()["total"]

    def check_level_up(self, current_level: str) -> Optional[str]:
        idx = LEVEL_ORDER.get(current_level, 0)
        if idx >= len(CEFR_LEVELS) - 1:
            return None
        next_level = CEFR_LEVELS[idx + 1]
        criteria = LEVEL_UP_CRITERIA.get(current_level, {})
        
        mastery = self.get_mastery(current_level)
        required_skills = criteria.get("skills_required", [])
        if not all(mastery.get(s, 0) >= criteria.get("min_mastery_avg", 0.7) for s in required_skills):
            return None
        
        sessions = self.get_sessions_at_level(current_level)
        if sessions < criteria.get("min_sessions", 8):
            return None
        
        vocab_count = self.get_vocab_count()
        if vocab_count < criteria.get("min_vocab", 300):
            return None
        
        return next_level

    def do_level_up(self, from_level: str, to_level: str):
        with self._conn() as c:
            mastery = self.get_mastery(from_level)
            avg = sum(mastery.values()) / len(mastery) if mastery else 0
            vocab = self.get_vocab_count()
            sessions = self.get_sessions_at_level(from_level)
            
            c.execute("""
                INSERT INTO level_history (from_level, to_level, sessions_spent, mastery_avg, vocab_count, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (from_level, to_level, sessions, sum(self.get_mastery(from_level).values())/max(1,len(self.get_mastery(from_level))), self.get_vocab_count(), self._now()))
            
            c.execute("DELETE FROM curriculum_progress WHERE level = ?", (from_level,))
            c.execute("DELETE FROM level_mastery WHERE level = ?", (from_level,))
            c.commit()

    def record_assessment(self, level_before: str, level_after: str, score: float, details: str):
        with self._conn() as c:
            c.execute("""
                INSERT INTO level_assessments (level_before, level_after, assessment_type, score, details, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (level_before, level_after, "conversation", score, details, self._now()))
            c.commit()

    def get_recommendations(self, level: str, limit: int = 5) -> List[Dict]:
        mastery = self.get_mastery(level)
        weak = sorted(mastery.items(), key=lambda x: x[1])[:3]
        curriculum = self.get_curriculum(level)
        recs = []
        for cat, mastery_val in weak:
            if cat not in curriculum:
                continue
            for item in curriculum[cat]:
                with self._conn() as c:
                    row = c.execute(
                        "SELECT mastery FROM curriculum_progress WHERE level = ? AND category = ? AND item = ?",
                        (level, cat, item)
                    ).fetchone()
                    if not row or row["mastery"] < 0.7:
                        recs.append({"category": cat, "item": item, "reason": f"weak {cat} ({mastery_val:.0%})"})
                        break
        return recs[:limit]

    def get_status_summary(self, level: str) -> Dict:
        mastery = self.get_mastery(level)
        sessions = self.get_sessions_at_level(level)
        vocab = self.get_vocab_count()
        next_level = self.check_level_up(level)
        criteria = LEVEL_UP_CRITERIA.get(level, {})
        return {
            "current_level": level,
            "mastery": mastery,
            "mastery_avg": sum(mastery.values()) / max(1, len(mastery)) if mastery else 0,
            "sessions_at_level": sessions,
            "vocab_count": self.get_vocab_count(),
            "next_level": next_level,
            "criteria": criteria,
            "ready_for_level_up": next_level is not None,
            "recommendations": self.get_recommendations(level)
        }