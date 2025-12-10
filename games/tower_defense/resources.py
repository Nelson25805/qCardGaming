# games/tower_defense/resources.py
from pathlib import Path
import pygame

EXTS_AUDIO = (".wav", ".ogg", ".mp3", ".flac")
EXTS_IMAGE = [".png", ".bmp", ".gif", ".jpg", ".jpeg", ".webp"]


def load_graphics(game, folder=None):
    """
    Populate game.graphics keys:
      - 'tower', 'creature', 'projectile', 'background', 'path'
    Search order: provided folder -> package assets -> global assets -> current folder.
    """
    pkg_assets = Path(__file__).resolve().parent / "assets" / "Graphics"
    candidates = []
    if folder:
        candidates.append(Path(folder))
    candidates += [pkg_assets, Path("assets") / "Graphics", Path("assets"), Path(".")]

    tower_img = None
    creature_img = None
    proj_img = None
    background_img = None
    path_img = None

    def load_surface(p):
        try:
            return pygame.image.load(str(p)).convert_alpha()
        except Exception:
            return None

    for d in candidates:
        if not d.exists() or not d.is_dir():
            continue
        for p in sorted(d.iterdir()):
            if p.suffix.lower() not in EXTS_IMAGE:
                continue
            surf = load_surface(p)
            if surf is None:
                continue
            name = p.stem.lower()
            if "tower" in name or "power" in name or "base" in name:
                if tower_img is None:
                    tower_img = surf
                continue
            if "creature" in name or "enemy" in name or "mob" in name:
                if creature_img is None:
                    creature_img = surf
                continue
            if (
                "proj" in name
                or "bullet" in name
                or "shot" in name
                or "missile" in name
            ):
                if proj_img is None:
                    proj_img = surf
                continue
            if any(
                k in name
                for k in ("background", "bg", "scene", "stage", "wall", "shelf", "wood")
            ):
                if background_img is None:
                    background_img = surf
                    continue
            if "path" in name or "road" in name or "track" in name:
                if path_img is None:
                    path_img = surf
                    continue

    game.graphics["tower"] = tower_img
    game.graphics["creature"] = creature_img
    game.graphics["projectile"] = proj_img
    if background_img is not None:
        game.graphics["background"] = background_img
    if path_img is not None:
        game.graphics["path"] = path_img


def load_sounds(game, folder=None):
    """
    Fill game.sfx_bank with all loadable sounds in candidate folders.
    Common keys we look for later: 'shoot','impact','spawn','die','jam'
    """
    pkg_assets = Path(__file__).resolve().parent / "assets" / "Sound Effects"
    candidates = []
    if folder:
        candidates.append(Path(folder))
    candidates += [
        pkg_assets,
        Path("assets") / "Sound Effects",
        Path("assets"),
        Path("."),
    ]

    for d in candidates:
        if not d.exists() or not d.is_dir():
            continue
        for p in sorted(d.iterdir()):
            if p.suffix.lower() in EXTS_AUDIO and p.is_file():
                try:
                    s = pygame.mixer.Sound(str(p))
                    game.sfx_bank[p.stem.lower()] = s
                except Exception:
                    # silently ignore bad sound files
                    pass

    # expose friendly attributes (may be None)
    game.snd_shoot = (
        game.sfx_bank.get("shoot")
        or game.sfx_bank.get("shot")
        or game.sfx_bank.get("fire")
    )
    game.snd_impact = game.sfx_bank.get("impact") or game.sfx_bank.get("hit")
    game.snd_spawn = game.sfx_bank.get("spawn")
    game.snd_die = game.sfx_bank.get("die") or game.sfx_bank.get("death")
    game.snd_jam = game.sfx_bank.get("jam")
