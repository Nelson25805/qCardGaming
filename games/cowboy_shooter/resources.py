# games/cowboy_shooter/resources.py
from pathlib import Path
import pygame

EXTS_AUDIO = (".wav", ".ogg", ".mp3", ".flac")
EXTS_IMAGE = [".png", ".bmp", ".gif", ".jpg", ".jpeg", ".webp"]


def load_graphics(game, folder=None):
    """
    Populate game.graphics with keys:
      - 'player' -> surface or None
      - 'bullet' -> surface or None
      - 'bottle_frames' -> list of surfaces
      - 'background' -> surface for the shelf/wall background
    Searches package assets first, then optional `folder`, then top-level assets.
    """
    pkg_assets = Path(__file__).resolve().parent / "assets" / "Graphics"
    candidates = []
    if folder:
        candidates.append(Path(folder))
    candidates += [pkg_assets, Path("assets") / "Graphics", Path("assets"), Path(".")]

    player_img = None
    bullet_img = None
    bottle_frames = []
    background_img = None

    def name_has_any(n, toks):
        ln = n.lower()
        for t in toks:
            if t in ln:
                return True
        return False

    # background name tokens - purposely avoid overly ambiguous tokens like "back"
    bg_tokens = ("shelf", "wall", "background", "scene", "stage", "wood", "plank")

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

            # Prefer explicit background images by name
            if background_img is None and name_has_any(name, bg_tokens):
                # Avoid selecting images that are clearly player/back-view named
                # e.g. "player_back" or "cowboy_back" -> treat as player instead of background
                if not any(
                    k in name for k in ("player", "cowboy", "backview", "back_view")
                ):
                    background_img = surf
                    # (do not `continue` here; we still want to allow other categories to pick up other files)
                    continue

            # bottle frames detection
            if "bottle" in name:
                if "intact" in name:
                    bottle_frames.insert(0, surf)
                elif "crack" in name:
                    bottle_frames.append(surf)
                elif "shatter" in name:
                    bottle_frames.append(surf)
                else:
                    bottle_frames.insert(0, surf)
                continue

            # player image detection
            if any(k in name for k in ("player", "cowboy", "backview", "back_view")):
                if player_img is None:
                    player_img = surf
                continue

            # bullet / shot detection
            if any(k in name for k in ("bullet", "shot", "projectile")):
                if bullet_img is None:
                    bullet_img = surf
                continue

            # fallback: if no background yet and filename still hints at shelf/wall, use it
            if background_img is None and name_has_any(
                name, ("shelf", "wall", "background")
            ):
                # again avoid accidentally picking player art
                if not any(k in name for k in ("player", "cowboy")):
                    background_img = surf
                    continue

    # assign back to game.graphics (no trailing comma)
    game.graphics["player"] = player_img
    game.graphics["bullet"] = bullet_img
    game.graphics["bottle_frames"] = bottle_frames
    if background_img is not None:
        game.graphics["background"] = background_img

    # Optional debug: uncomment to print what was loaded at runtime
    # print("resources.load_graphics: player=", getattr(player_img, "get_size", lambda: None)(),
    #       "bullet=", getattr(bullet_img, "get_size", lambda: None)(),
    #       "bottles=", len(bottle_frames),
    #       "background=", getattr(background_img, "get_size", lambda: None)())
