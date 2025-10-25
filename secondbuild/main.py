"""
main.py - modular launcher with main menu to pick game and question CSV.
Place this launcher in the same folder as the modular_study_invaders package (or run from inside it).
It lists CSV files in the current directory and allows picking a file or using a file dialog.
"""

import pygame, sys, os
from pathlib import Path
from games.space_game import SpaceGame
import utils

BASE = Path('.')

def list_csv_files(folder):
    return sorted([p.name for p in Path(folder).glob("*.csv")])

def run_menu():
    pygame.init()
    screen = pygame.display.set_mode((800,600))
    pygame.display.set_caption("Study Gamify - Main Menu")
    clock = pygame.time.Clock()
    font = pygame.font.Font(None, 28)
    big = pygame.font.Font(None, 40)

    # default question file (try questions.csv)
    selected_csv = None
    csvs = list_csv_files('.')
    if 'questions.csv' in csvs:
        selected_csv = 'questions.csv'
    elif csvs:
        selected_csv = csvs[0]

    while True:
        dt = clock.tick(60)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit(0)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx,my = event.pos
                # Play Space Invaders button
                play_rect = utils.button_rect(400, 180, w=360, h=60)
                file_rect = utils.button_rect(400, 280, w=360, h=50)
                quit_rect = utils.button_rect(400, 420, w=200, h=44)
                if play_rect.collidepoint(mx,my):
                    if selected_csv is None:
                        print("Choose a question CSV first.")
                    else:
                        # launch game
                        game = SpaceGame(selected_csv)
                        game.load_sounds('.')  # load sounds from current folder
                        result = game.run()
                        # after returning, go back to menu
                        csvs = list_csv_files('.')
                elif file_rect.collidepoint(mx,my):
                    # cycle through available csvs
                    csvs = list_csv_files('.')
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
                elif quit_rect.collidepoint(mx,my):
                    pygame.quit()
                    sys.exit(0)

        screen.fill((18,18,28))
        title = big.render("Study Gamify", True, (255,255,255))
        screen.blit(title, (400 - title.get_width()//2, 30))

        # draw buttons
        play_rect = utils.button_rect(400, 180, w=360, h=60)
        pygame.draw.rect(screen, (60,120,180), play_rect, border_radius=8)
        screen.blit(font.render("Play: Space Invaders (Study Mode)", True, (255,255,255)), (play_rect.x+14, play_rect.y+18))

        file_rect = utils.button_rect(400, 280, w=360, h=50)
        pygame.draw.rect(screen, (90,90,90), file_rect, border_radius=8)
        file_text = selected_csv if selected_csv else "No CSV found. Drop questions.csv here."
        screen.blit(font.render(f"Questions file: {file_text}", True, (255,255,255)), (file_rect.x+14, file_rect.y+14))

        csvs = list_csv_files('.')
        quit_rect = utils.button_rect(400, 420, w=200, h=44)
        pygame.draw.rect(screen, (120,60,80), quit_rect, border_radius=8)
        screen.blit(font.render("Quit", True, (255,255,255)), (quit_rect.x+64, quit_rect.y+10))

        hint = font.render("Click 'Questions file' to cycle CSVs in this folder.", True, (180,180,180))
        screen.blit(hint, (400 - hint.get_width()//2, 340))

        pygame.display.flip()

if __name__ == "__main__":
    run_menu()
