from pathlib import Path
import pygame

EXTS_AUDIO = ('.wav', '.ogg', '.mp3', '.flac')
EXTS_IMAGE = ['.png', '.bmp', '.gif', '.jpg', '.jpeg', '.webp']

def load_graphics(game, folder=None):
    pkg_assets = Path(__file__).resolve().parent / 'assets' / 'Graphics'
    candidates = []
    if folder:
        candidates.append(Path(folder))
    candidates += [pkg_assets, Path('assets') / 'Graphics', Path('assets'), Path('.')]
    player_img = None
    bullet_img = None
    bottle_frames = []
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
            if 'player' in name or 'cowboy' in name or 'back' in name:
                if player_img is None:
                    player_img = surf
            elif 'bullet' in name or 'shot' in name:
                if bullet_img is None:
                    bullet_img = surf
            elif 'bottle' in name:
                # maintain approximate ordering by name: intact, crack, shatter
                if 'intact' in name:
                    bottle_frames.insert(0, surf)
                elif 'crack' in name:
                    bottle_frames.append(surf)
                elif 'shatter' in name:
                    bottle_frames.append(surf)
                else:
                    bottle_frames.insert(0, surf)
    game.graphics['player'] = player_img
    game.graphics['bullet'] = bullet_img
    game.graphics['bottle_frames'] = bottle_frames

def load_sounds(game, folder=None):
    pkg_assets = Path(__file__).resolve().parent / 'assets' / 'Sound Effects'
    cand_dirs = []
    if folder:
        cand_dirs.append(Path(folder))
    cand_dirs += [pkg_assets, Path('assets') / 'Sound Effects', Path('assets'), Path('.')]

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

    # provide friendly names
    game.snd_shot = game.sfx_bank.get('shot') or game.sfx_bank.get('shoot')
    game.snd_break = game.sfx_bank.get('break') or game.sfx_bank.get('impact')
    game.snd_jam = game.sfx_bank.get('jam') or game.sfx_bank.get('click')
