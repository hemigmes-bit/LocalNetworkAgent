from datetime import datetime, timedelta
from typing import List, Dict, Tuple
from dataclasses import dataclass

@dataclass
class SRSItem:
    word: str
    translation: str
    example: str
    interval: int = 1
    repetitions: int = 0
    ease_factor: float = 2.5
    next_review: str = ""
    last_reviewed: str = ""


class SimpleSRS:
    @staticmethod
    def calculate_next(item: Dict, quality: int) -> Tuple[int, int, float, str]:
        interval = item.get('interval', 1)
        repetitions = item.get('repetitions', 0)
        ease = item.get('ease_factor', 2.5)

        if quality < 3:
            repetitions = 0
            interval = 1
        else:
            if repetitions == 0:
                interval = 1
            elif repetitions == 1:
                interval = 6
            else:
                interval = round(interval * item.get('ease_factor', 2.5))
            repetitions += 1

        ease = max(1.3, ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))

        next_review = (datetime.now() + timedelta(days=interval)).date().isoformat()

        return interval, repetitions, max(1.3, ease), next_review

# Instancia global
SRS = SimpleSRS()