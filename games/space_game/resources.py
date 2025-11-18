"""Resource loading helpers (images, sounds, music) for the Space Game."""
from pathlib import Path
import pygame
import math

EXTS_AUDIO = (".wav", ".ogg", ".mp3", ".flac")
EXTS_IMAGE = [".png", ".bmp", ".gif", ".jpg", ".jpeg", ".webp"]

def try_load_sound(path):
    try:
        return pygame.mixer.Sound(str(path))
    except Exception:
        return None

def load_sounds(game, folder=None):
    """Populate game.fire_snd, game.hit_snd and game.sfx_bank by searching candidate dirs."""
    base = Path(folder) if folder else Path(".")
    cand_dirs = []
    if folder:
        cand_dirs.append(Path(folder))
    cand_dirs += [
        Path("assets") / "Sound Effects",
        Path("assets") / "SoundEffects",
        Path("assets") / "Sound_Effects",
        Path("assets") / "sound effects",
        Path("assets"),
        Path("."),
    ]

    def find_file_by_stem(stem):
        for d in cand_dirs:
            if not d.exists() or not d.is_dir():
                continue
            for ext in EXTS_AUDIO:
                p = d / f"{stem}{ext}"
                if p.exists() and p.is_file():
                    return p
        # fuzzy: any file containing stem in name
        for d in cand_dirs:
            if not d.exists() or not d.is_dir():
                continue
            for p in sorted(d.iterdir()):
                if p.suffix.lower() in EXTS_AUDIO and stem.lower() in p.stem.lower():
                    return p
        return None

    f = find_file_by_stem("fire")
    game.fire_snd = try_load_sound(f) if f else None
    h = find_file_by_stem("hit")
    game.hit_snd = try_load_sound(h) if h else None

    game.sfx_bank = {}
    for d in cand_dirs:
        if not d.exists() or not d.is_dir():
            continue
        for p in sorted(d.iterdir()):
            if p.suffix.lower() in EXTS_AUDIO and p.is_file():
                snd = try_load_sound(p)
                if snd:
                    game.sfx_bank[p.stem.lower()] = snd

    # fallbacks for common names
    for k in ("shot", "shoot"):
        if game.fire_snd is None and k in game.sfx_bank:
            game.fire_snd = game.sfx_bank[k]
    for k in ("explode", "impact"):
        if game.hit_snd is None and k in game.sfx_bank:
            game.hit_snd = game.sfx_bank[k]

def load_graphics(game, folder=None):
    """Attempt to load invader/player/bullet images from asset folders."""
    candidates = []
    if folder:
        candidates.append(Path(folder))
    candidates += [
        Path("assets") / "Graphics",
        Path("assets") / "graphics",
        Path("assets"),
        Path("."),
    ]
    inv_images = []
    player_img = None
    bullet_img = None

    for d in candidates:
        if not d.exists() or not d.is_dir():
            continue
        for p in sorted(d.iterdir()):
            if p.suffix.lower() not in EXTS_IMAGE:
                continue
            name = p.stem.lower()
            try:
                surf = pygame.image.load(str(p)).convert_alpha()
            except Exception:
                continue
            if "invader" in name or "alien" in name or "enemy" in name:
                inv_images.append(surf)
            elif "player" in name or "ship" in name:
                if player_img is None:
                    player_img = surf
            elif "bullet" in name or "shot" in name or "projectile" in name:
                if bullet_img is None:
                    bullet_img = surf

    game.graphics["invaders"] = inv_images
    game.graphics["player"] = player_img
    game.graphics["bullet"] = bullet_img

def start_music(game):
    if not getattr(game, "music_enabled", False):
        return False
    mc = getattr(game.settings, "music_choice", "") or ""
    if not mc:
        return False
    candidates = [
        Path("assets") / "Music" / mc,
        Path("assets") / "music" / mc,
        Path("music") / mc,
        Path(mc),
    ]
    for p in candidates:
        if p.exists() and p.is_file():
            try:
                pygame.mixer.music.load(str(p))
                pygame.mixer.music.play(-1)
                return True
            except Exception:
                pass
    return False

def stop_music(game):
    try:
        pygame.mixer.music.stop()
    except Exception:
        pass
