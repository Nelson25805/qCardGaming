# games/tower_defense/resources.py
from pathlib import Path
import pygame

EXTS_AUDIO = (".wav", ".ogg", ".mp3", ".flac")
EXTS_IMAGE = (".png", ".bmp", ".gif", ".jpg", ".jpeg", ".webp")


def load_graphics(game, folder=None):
    """
    Fill game.graphics with:
      - 'course' : surface for track background (optional)
      - 'tower'  : surface for towers
      - 'creature' : surface for enemies
      - 'projectile' : surface for projectiles
    If not found, leave as None and game will draw placeholders.
    """
    pkg_assets = Path(__file__).resolve().parent / "assets" / "Graphics"
    candidates = []
    if folder:
        candidates.append(Path(folder))
    candidates += [pkg_assets, Path("assets") / "Graphics", Path("assets"), Path(".")]

    course = None
    tower = None
    creature = None
    projectile = None

    for d in candidates:
        if not d.exists() or not d.is_dir():
            continue
        for p in sorted(d.iterdir()):
            if p.suffix.lower() not in EXTS_IMAGE:
                continue
            try:
                surf = pygame.image.load(str(p)).convert_alpha()
            except Exception:
                continue
            name = p.stem.lower()
            if any(t in name for t in ("track", "course", "path", "background", "map")):
                if course is None:
                    course = surf
                continue
            if any(t in name for t in ("tower", "turret")):
                if tower is None:
                    tower = surf
                continue
            if any(t in name for t in ("creature", "enemy", "monster")):
                if creature is None:
                    creature = surf
                continue
            if any(t in name for t in ("projectile", "bullet", "shot")):
                if projectile is None:
                    projectile = surf
                continue

    game.graphics.setdefault("course", course)
    game.graphics.setdefault("tower", tower)
    game.graphics.setdefault("creature", creature)
    game.graphics.setdefault("projectile", projectile)


def load_sounds(game, folder=None):
    """
    Populate game.sfx_bank with available sounds (keys are lowercase stems).
    Looks for the usual audio files in provided folder, then package assets, then top-level assets.
    """
    pkg_assets = Path(__file__).resolve().parent / "assets" / "Sound Effects"
    cand_dirs = []
    if folder:
        cand_dirs.append(Path(folder))
    cand_dirs += [
        pkg_assets,
        Path("assets") / "Sound Effects",
        Path("assets"),
        Path("."),
    ]

    def try_load(p):
        try:
            return pygame.mixer.Sound(str(p))
        except Exception:
            return None

    for d in cand_dirs:
        if not d.exists() or not d.is_dir():
            continue
        for p in sorted(d.iterdir()):
            if p.suffix.lower() in EXTS_AUDIO and p.is_file():
                key = p.stem.lower()
                s = try_load(p)
                if s:
                    game.sfx_bank[key] = s

    # friendly aliases
    game.snd_shoot = (
        game.sfx_bank.get("shoot")
        or game.sfx_bank.get("shooting")
        or game.sfx_bank.get("fire")
    )
    game.snd_hit = (
        game.sfx_bank.get("hit")
        or game.sfx_bank.get("impact")
        or game.sfx_bank.get("break")
    )
    game.snd_rush = (
        game.sfx_bank.get("rush")
        or game.sfx_bank.get("alarm")
        or game.sfx_bank.get("rush_to_goal")
    )
