"""Configuration module for Emma Bilingüe."""
import os
import json
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class Unit:
    id: str
    title: str
    vocabulary: List[str]
    grammar: List[str]
    phrases: List[str]
    objectives: List[str]


@dataclass
class Level:
    level: str
    name: str
    description: str
    vocabulary_target: int
    grammar_topics: List[str]
    units: List[Unit]
    assessment: Dict


class Curriculum:
    def __init__(self, curriculum_dir: str = None):
        if curriculum_dir is None:
            # Path: emma_bilingue/python/src/main/python/emma_core/curriculum.py
            # Go up 6 levels to reach emma_bilingue
            base = Path(__file__).parent.parent.parent.parent.parent.parent
            curriculum_dir = str(base / "curriculum")
        self.curriculum_dir = Path(curriculum_dir)
        self.levels: Dict[str, Level] = {}
        self._load_all_levels()

    def _load_all_levels(self):
        if not self.curriculum_dir.exists():
            print("[WARNING] Directorio curriculum no encontrado: " + str(self.curriculum_dir))
            return

        for yaml_file in self.curriculum_dir.glob("*.yaml"):
            try:
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)

                level_key = data['level']
                units = [Unit(**u) for u in data.get('units', [])]

                self.levels[level_key] = Level(
                    level=data['level'],
                    name=data['name'],
                    description=data['description'],
                    vocabulary_target=data['vocabulary_target'],
                    grammar_topics=data['grammar_topics'],
                    units=units,
                    assessment=data.get('assessment', {})
                )
                print(f"✅ Nivel {level_key} cargado: {len(units)} unidades")
            except Exception as e:
                print(f"❌ Error cargando {yaml_file}: {e}")

    def get_level(self, level: str) -> Optional[Level]:
        return self.levels.get(level.upper())

    def get_unit(self, level: str, unit_id: str) -> Optional[Unit]:
        level_obj = self.get_level(level)
        if level_obj:
            for unit in level_obj.units:
                if unit.id == unit_id:
                    return unit
        return None

    def get_all_levels(self) -> List[str]:
        return sorted(self.levels.keys())

    def get_next_unit(self, level: str, current_unit_id: str) -> Optional[Unit]:
        level_obj = self.get_level(level)
        if not level_obj:
            return None

        for i, unit in enumerate(level_obj.units):
            if unit.id == current_unit_id and i + 1 < len(level_obj.units):
                return level_obj.units[i + 1]
        return None

    def get_progress_info(self, level: str, completed_units: List[str]) -> Dict:
        level_obj = self.get_level(level)
        if not level_obj:
            return {}

        total = len(level_obj.units)
        completed = len([u for u in level_obj.units if u.id in completed_units])

        return {
            "level": level,
            "total_units": total,
            "completed": completed,
            "percentage": (completed / total * 100) if total > 0 else 0,
            "next_unit": self.get_next_unit(level, completed_units[-1]) if completed_units else level_obj.units[0] if level_obj.units else None
        }


# Instancia global
CURRICULUM = Curriculum()

def get_curriculum() -> "Curriculum":
    return CURRICULUM