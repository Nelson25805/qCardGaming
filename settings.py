"""
settings.py
Defines Settings data structure, load/save, and default values.
"""

import json
from dataclasses import dataclass, asdict, field
from pathlib import Path

SETTINGS_FILE = "settings.json"

@dataclass
class Settings:
    # question order: "top", "bottom", "random"
    question_order: str = "random"
    # time between questions before losing a life: store as seconds or None for unlimited
    time_between_questions: float = None  # None means unlimited
    # total time for session in seconds or None for unlimited
    total_time: float = None
    # lives: integer or None for unlimited
    lives: int = 3
    # sound effects on/off
    sfx: bool = True
    # music on/off and selection
    music: bool = False
    music_choice: str = ""  # filename
    # question amount mode: "one_each" or "loop"
    question_mode: str = "loop"
    # optional gameplay tweaks
    enemy_speed_multiplier: float = 1.0
    muzzle_flash: bool = True

    @staticmethod
    def load(path: str = SETTINGS_FILE):
        p = Path(path)
        if not p.exists():
            return Settings()
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return Settings(**data)
        except Exception:
            return Settings()

    def save(self, path: str = SETTINGS_FILE):
        p = Path(path)
        p.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
