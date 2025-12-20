from pathlib import Path
import pygame

EXTS_IMAGE = (".png", ".bmp", ".gif", ".jpg", ".jpeg", ".webp")
EXTS_AUDIO = (".wav", ".ogg", ".mp3", ".flac")


def load_graphics(game, folder=None):
    pkg_assets = Path(__file__).resolve().parent / "assets" / "Graphics"
    candidates = []
    if folder:
        candidates.append(Path(folder))
    candidates += [pkg_assets, Path("assets") / "Graphics", Path("assets"), Path(".")]
    keys = {"course": None, "creature": None, "tower": None, "projectile": None}
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
            if "course" in name or "map" in name or "track" in name:
                keys["course"] = surf
            elif "creature" in name or "enemy" in name:
                keys["creature"] = surf
            elif "tower" in name:
                keys["tower"] = surf
            elif "projectile" in name or "bullet" in name or "shot" in name:
                keys["projectile"] = surf
    for k, v in keys.items():
        if v is not None:
            game.graphics[k] = v


def load_sounds(game, folder=None):
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

    def try_load(p):
        try:
            return pygame.mixer.Sound(str(p))
        except Exception:
            return None

    for d in candidates:
        if not d.exists() or not d.is_dir():
            continue
        for p in sorted(d.iterdir()):
            if p.suffix.lower() in EXTS_AUDIO and p.is_file():
                key = p.stem.lower()
                s = try_load(p)
                if s:
                    game.sfx_bank[key] = s
