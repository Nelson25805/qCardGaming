"""
main.py - modular launcher with main menu and settings screen
"""

import pygame, sys, os
from pathlib import Path
from games.space_game import SpaceGame
import utils
from settings import Settings

BASE = Path(".")


def list_csv_files(folder):
    return sorted([p.name for p in Path(folder).glob("*.csv")])


def list_music_files(folder):
    exts = (".mp3", ".ogg", ".wav", ".flac")
    return sorted([p.name for p in Path(folder).glob("*") if p.suffix.lower() in exts])


def run_settings_screen(screen, settings: Settings):
    clock = pygame.time.Clock()
    font = pygame.font.Font(None, 26)
    big = pygame.font.Font(None, 36)

    opts = [
        (
            "Question order",
            ["top", "bottom", "random"],
            getattr(settings, "question_order"),
        ),
        (
            "Time between Qs",
            ["unlimited", "10s", "30s", "60s", "120s"],
            (
                "unlimited"
                if settings.time_between_questions is None
                else f"{int(settings.time_between_questions)}s"
            ),
        ),
        (
            "Total time",
            ["unlimited", "5m", "15m", "30m"],
            (
                "unlimited"
                if settings.total_time is None
                else f"{int(settings.total_time)}s"
            ),
        ),
        (
            "Lives",
            ["3", "5", "10", "unlimited"],
            str(settings.lives) if settings.lives is not None else "unlimited",
        ),
        ("SFX", ["on", "off"], "on" if settings.sfx else "off"),
        ("Music", ["off", "on"], "on" if settings.music else "off"),
        ("Question mode", ["loop", "one_each"], settings.question_mode),
        ("Enemy speed", ["0.75", "1.0", "1.5"], str(settings.enemy_speed_multiplier)),
        ("Muzzle flash", ["on", "off"], "on" if settings.muzzle_flash else "off"),
    ]

    sel = 0
    running = True
    while running:
        dt = clock.tick(30)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_UP:
                    sel = max(0, sel - 1)
                elif event.key == pygame.K_DOWN:
                    sel = min(len(opts) - 1, sel + 1)
                elif event.key == pygame.K_RIGHT or event.key == pygame.K_RETURN:
                    # cycle selected option to next
                    label, choices, cur = opts[sel]
                    idx = choices.index(cur) if cur in choices else 0
                    idx = (idx + 1) % len(choices)
                    opts[sel] = (label, choices, choices[idx])
                elif event.key == pygame.K_LEFT:
                    label, choices, cur = opts[sel]
                    idx = choices.index(cur) if cur in choices else 0
                    idx = (idx - 1) % len(choices)
                    opts[sel] = (label, choices, choices[idx])
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                # Back and Save buttons as rectangles
                back = utils.button_rect(100, 520, w=140, h=44)
                save = utils.button_rect(700, 520, w=140, h=44)
                if back.collidepoint(mx, my):
                    running = False
                if save.collidepoint(mx, my):
                    # apply options into settings and save
                    for label, choices, cur in opts:
                        if label == "Question order":
                            settings.question_order = cur
                        elif label == "Time between Qs":
                            settings.time_between_questions = (
                                None if cur == "unlimited" else int(cur.rstrip("s"))
                            )
                        elif label == "Total time":
                            settings.total_time = (
                                None
                                if cur == "unlimited"
                                else (
                                    int(cur.rstrip("m")) * 60
                                    if cur.endswith("m")
                                    else int(cur.rstrip("s"))
                                )
                            )
                        elif label == "Lives":
                            settings.lives = None if cur == "unlimited" else int(cur)
                        elif label == "SFX":
                            settings.sfx = cur == "on"
                        elif label == "Music":
                            settings.music = cur == "on"
                        elif label == "Question mode":
                            settings.question_mode = cur
                        elif label == "Enemy speed":
                            settings.enemy_speed_multiplier = float(cur)
                        elif label == "Muzzle flash":
                            settings.muzzle_flash = cur == "on"
                    settings.save()
                    running = False

        # draw
        screen.fill((18, 18, 28))
        title = big.render("Settings", True, (255, 255, 255))
        screen.blit(title, (400 - title.get_width() // 2, 24))

        # draw options
        base_y = 100
        for i, (label, choices, cur) in enumerate(opts):
            y = base_y + i * 46
            col = (255, 240, 200) if i == sel else (200, 200, 200)
            screen.blit(font.render(label, True, col), (80, y))
            screen.blit(font.render(str(cur), True, (180, 180, 255)), (420, y))

        # draw back/save buttons
        back = utils.button_rect(100, 520, w=140, h=44)
        pygame.draw.rect(screen, (80, 80, 120), back, border_radius=8)
        screen.blit(
            font.render("Back", True, (255, 255, 255)), (back.x + 38, back.y + 12)
        )
        save = utils.button_rect(700, 520, w=140, h=44)
        pygame.draw.rect(screen, (50, 150, 80), save, border_radius=8)
        screen.blit(
            font.render("Save", True, (255, 255, 255)), (save.x + 44, save.y + 12)
        )

        pygame.display.flip()

    return "ok"


def run_menu():
    pygame.init()
    screen = pygame.display.set_mode((800, 600))
    pygame.display.set_caption("Study Gamify - Main Menu")
    clock = pygame.time.Clock()
    font = pygame.font.Font(None, 28)
    big = pygame.font.Font(None, 40)

    # load or create settings
    settings = Settings.load()

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
                if play_rect.collidepoint(mx, my):
                    if selected_csv is None:
                        print("Choose a question CSV first.")
                    else:
                        game = SpaceGame(selected_csv, settings=settings)
                        game.load_sounds(".")  # load sounds from current folder
                        result = game.run()
                        csvs = list_csv_files(".")
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
                    run_settings_screen(screen, settings)
                elif quit_rect.collidepoint(mx, my):
                    pygame.quit()
                    sys.exit(0)

        screen.fill((18, 18, 28))
        title = big.render("Study Gamify", True, (255, 255, 255))
        screen.blit(title, (400 - title.get_width() // 2, 30))

        # draw buttons
        play_rect = utils.button_rect(400, 170, w=360, h=60)
        pygame.draw.rect(screen, (60, 120, 180), play_rect, border_radius=8)
        screen.blit(
            font.render("Play: Space Invaders (Study Mode)", True, (255, 255, 255)),
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
