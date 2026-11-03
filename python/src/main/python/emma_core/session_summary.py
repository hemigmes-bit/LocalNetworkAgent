from typing import List, Dict
from datetime import datetime
from dataclasses import dataclass
from typing import Optional

@dataclass
class TurnSummary:
    turn: int
    user_text: str
    spoken: str
    corrections: List[Dict]
    vocabulary: List[Dict]
    time_ms: int

@dataclass
class SessionSummary:
    session_id: int
    start_time: str
    end_time: str
    total_turns: int
    total_time_ms: int
    total_corrections: int
    vocabulary_added: int
    turns: List[Dict]
    review_items: List[Dict]

class SessionSummarizer:
    def __init__(self, profile_manager):
        self.profile = profile_manager

    def generate_summary(self, session_id: int, turns: List[Dict],
                         start_time: datetime, end_time: datetime) -> Dict:
        total_turns = len([t for t in turns if t.get('completed', True)])
        total_corrections = sum(len(t.get('corrections', [])) for t in turns)
        vocabulary_added = sum(len(t.get('vocabulary', [])) for t in turns)
        total_time = sum(t.get('time_ms', 0) for t in turns)

        review_items = self._get_review_items(3)

        summary = {
            "session_date": datetime.now().isoformat(),
            "total_turns": len(turns),
            "total_time_minutes": round(sum(t.get('time_ms', 0) for t in turns) / 60000, 1),
            "total_corrections": sum(len(t.get('corrections', [])) for t in turns),
            "vocabulary_added": sum(len(t.get('vocabulary', [])) for t in turns),
            "avg_time_per_turn": round(sum(t.get('time_ms', 0) for t in turns) / max(1, len(turns)) / 1000, 1),
            "turns": [
                {
                    "turn": t.get('turn'),
                    "user_text": t.get('user_text', ''),
                    "spoken": t.get('spoken', ''),
                    "corrections_count": len(t.get('corrections', [])),
                    "corrections": t.get('corrections', []),
                    "vocabulary": t.get('vocabulary', []),
                    "time_ms": t.get('time_ms', 0)
                }
                for t in turns
            ],
            "review_items": self._get_review_items(3)
        }

        return summary

    def _get_review_items(self, count: int = 3) -> List[Dict]:
        items = []

        errors = self.profile.get_recurring_errors(limit=5)
        for err in errors[:2]:
            items.append({
                "type": "error_review",
                "priority": "high",
                "content": f"Corrige: '{err['original_text']}' -> '{err['corrected_text']}'",
                "explanation": err.get('explanation', ''),
                "count": err['count']
            })

        try:
            vocab_due = self.profile.get_due_reviews(limit=5)
            for voc in vocab_due[:1]:
                items.append({
                    "type": "vocabulary_review",
                    "priority": "medium",
                    "content": f"Repasa: '{voc['word']}' = {voc['translation']}",
                    "example": voc.get('example', ''),
                    "interval": voc.get('interval', 1)
                })
        except:
            pass

        return items[:3]

    def print_summary(self, summary: Dict):
        print("\n" + "="*60)
        print("📋 RESUMEN DE SESIÓN")
        print("="*60)
        print(f"📅 Fecha: {summary['session_date'][:10]}")
        print(f"🔄 Turnos: {summary['total_turns']}")
        print(f"⏱️ Tiempo total: {summary['total_time_minutes']} min")
        print(f"✏️ Correcciones: {summary['total_corrections']}")
        print(f"📚 Vocabulario nuevo: {summary['vocabulary_added']}")
        print(f"⏱️ Tiempo/turno: {summary['avg_time_per_turn']}s")

        print("\n📝 PARA REPASAR (3 items):")
        for i, item in enumerate(summary['review_items'], 1):
            print(f"  {i}. [{item['priority'].upper()}] {item['content']}")
            if item.get('explanation'):
                print(f"     💡 {item['explanation']}")

        print("="*60)

SESSION_SUMMARIZER = None

def get_session_summarizer(profile_manager):
    global SESSION_SUMMARIZER
    if SESSION_SUMMARIZER is None:
        SESSION_SUMMARIZER = SessionSummarizer(profile_manager)
    return SESSION_SUMMARIZER