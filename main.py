# main.py - modular launcher with game chooser and settings aware of selected game
import pygame, sys, os, importlib
from pathlib import Path
import utils
from settings import Settings, run_settings_screen

BASE = Path(".")


def list_csv_files(folder):
    return sorted([p.name for p in Path(folder).glob("*.csv")])


def discover_games():
    games = []
    gd = Path("games")
    if not gd.exists() or not gd.is_dir():
        return games
    for d in sorted(gd.iterdir()):
        if not d.is_dir() or d.name.startswith("__"):
            continue
        pkg = f"games.{d.name}"
        try:
            mod = importlib.import_module(pkg)
        except Exception:
            continue
        cls = getattr(mod, "Game", None)
        if cls is None:
            for name in dir(mod):
                if name.endswith("Game"):
                    cls = getattr(mod, name)
                    break
        if cls is not None:
            label = d.name.replace("_", " ").title()
            games.append((d.name, label, cls))
    return games


def run_menu():
    pygame.init()
    screen = pygame.display.set_mode((800, 600))
    pygame.display.set_caption("Study Gamify - Main Menu")
    clock = pygame.time.Clock()
    font = pygame.font.Font(None, 28)
    big = pygame.font.Font(None, 40)

    # load or create settings
    settings = Settings.load()

    # discover games
    games = discover_games()
    game_idx = 0 if games else -1

    # default question file (try questions.csv)
    selected_csv = None
    csvs = list_csv_files(".")
    if "questions.csv" in csvs:
        selected_csv = "questions.csv"
    elif csvs:
        selected_csv = csvs[0]

    while True:
        dt = clock.tick(60)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit(0)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                play_rect = utils.button_rect(400, 170, w=360, h=60)
                file_rect = utils.button_rect(400, 260, w=360, h=50)
                settings_rect = utils.button_rect(400, 350, w=360, h=50)
                quit_rect = utils.button_rect(400, 450, w=200, h=44)
                choose_game_rect = utils.button_rect(400, 110, w=360, h=44)
                if play_rect.collidepoint(mx, my):
                    if selected_csv is None:
                        print("Choose a question CSV first.")
                    else:
                        if game_idx >= 0 and game_idx < len(games):
                            pkgname, label, cls = games[game_idx]
                            game = cls(selected_csv, settings=settings)
                            # let game load its sounds from its package assets first, then fallback
                            try:
                                ls = getattr(game, "load_sounds", None)
                                if callable(ls):
                                    ls(Path("games") / pkgname / "assets")
                            except Exception:
                                pass
                            result = game.run()
                            csvs = list_csv_files(".")
                        else:
                            print("No game selected.")
                elif file_rect.collidepoint(mx, my):
                    csvs = list_csv_files(".")
                    if not csvs:
                        selected_csv = None
                    else:
                        if selected_csv is None:
                            selected_csv = csvs[0]
                        else:
                            try:
                                idx = csvs.index(selected_csv)
                                idx = (idx + 1) % len(csvs)
                                selected_csv = csvs[idx]
                            except ValueError:
                                selected_csv = csvs[0]
                elif settings_rect.collidepoint(mx, my):
                    # pass current selected game folder name to settings so music list can prioritize game-local music
                    current_game = (
                        games[game_idx][0] if (game_idx >= 0 and games) else None
                    )
                    run_settings_screen(screen, settings, current_game=current_game)
                elif quit_rect.collidepoint(mx, my):
                    pygame.quit()
                    sys.exit(0)
                elif choose_game_rect.collidepoint(mx, my):
                    if games:
                        game_idx = (game_idx + 1) % len(games)

        screen.fill((18, 18, 28))
        title = big.render("Study Gamify", True, (255, 255, 255))
        screen.blit(title, (400 - title.get_width() // 2, 30))

        choose_game_rect = utils.button_rect(400, 110, w=360, h=44)
        pygame.draw.rect(screen, (80, 120, 90), choose_game_rect, border_radius=8)
        game_label = "None"
        if game_idx >= 0 and games:
            game_label = games[game_idx][1]
        screen.blit(
            font.render(f"Game: {game_label}", True, (255, 255, 255)),
            (choose_game_rect.x + 14, choose_game_rect.y + 10),
        )

        play_rect = utils.button_rect(400, 170, w=360, h=60)
        pygame.draw.rect(screen, (60, 120, 180), play_rect, border_radius=8)
        screen.blit(
            font.render("Play", True, (255, 255, 255)),
            (play_rect.x + 14, play_rect.y + 18),
        )

        file_rect = utils.button_rect(400, 260, w=360, h=50)
        pygame.draw.rect(screen, (90, 90, 90), file_rect, border_radius=8)
        file_text = (
            selected_csv if selected_csv else "No CSV found. Drop questions.csv here."
        )
        screen.blit(
            font.render(f"Questions file: {file_text}", True, (255, 255, 255)),
            (file_rect.x + 14, file_rect.y + 14),
        )

        settings_rect = utils.button_rect(400, 350, w=360, h=50)
        pygame.draw.rect(screen, (100, 90, 140), settings_rect, border_radius=8)
        screen.blit(
            font.render("Settings", True, (255, 255, 255)),
            (settings_rect.x + 14, settings_rect.y + 14),
        )

        csvs = list_csv_files(".")
        quit_rect = utils.button_rect(400, 450, w=200, h=44)
        pygame.draw.rect(screen, (120, 60, 80), quit_rect, border_radius=8)
        screen.blit(
            font.render("Quit", True, (255, 255, 255)),
            (quit_rect.x + 64, quit_rect.y + 10),
        )

        hint = font.render(
            "Click 'Questions file' to cycle CSVs in this folder.",
            True,
            (180, 180, 180),
        )
        screen.blit(hint, (400 - hint.get_width() // 2, 520))

        pygame.display.flip()


if __name__ == "__main__":
    run_menu()
