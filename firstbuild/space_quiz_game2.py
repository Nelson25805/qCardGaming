"""
space_quiz_game_trajectory_v3.py

Improved bullet trajectory logic:
 - Bullets use a normalized direction vector toward the chosen target and a fixed bullet speed magnitude.
 - Bullet keeps float positions (posx,posy) for smooth movement and accurate travel.
 - Forced-hit logic uses a proximity (distance) check instead of only vertical passing.
 - Keeps muzzle flash and sounds as before.

Drop this file, questions.csv, and your sound files (fire.wav/hit.wav) into the same folder and run:
    python space_quiz_game_trajectory_v3.py
"""

import pygame
import csv
import random
import sys
from pathlib import Path
import math

# CONFIG
SCREEN_W, SCREEN_H = 800, 600
FPS = 60
QUESTIONS_CSV = "questions.csv"
FONT_NAME = None  # default font
PLAYER_SPEED = 6
# BULLET_SPEED_MAG is the overall bullet speed (pixels per frame)
BULLET_SPEED_MAG = 12.0
ENEMY_ROWS = 3
ENEMY_COLS = 6
ENEMY_PADDING = 10
LIVES = 3


# ----------------------- Utilities -----------------------
def load_questions(csv_path):
    rows = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            if r.get("question") and r.get("answer"):
                rows.append({"id": r.get("id"), "q": r["question"], "a": r["answer"]})
    return rows


def is_number(s):
    try:
        float(s)
        return True
    except:
        return False


def make_distractors(correct, pool):
    candidates = set()
    if is_number(correct):
        try:
            val = float(correct)
            nums = [val - 1, val + 1, val + 2, val - 2, val * 10]
            for n in nums:
                if len(candidates) >= 3:
                    break
                if n != val:
                    s = str(int(n)) if abs(n - int(n)) < 1e-9 else str(n)
                    if s != correct:
                        candidates.add(s)
        except:
            pass
    for p in pool:
        if len(candidates) >= 3:
            break
        if p != correct:
            candidates.add(p)
    i = 0
    while len(candidates) < 3:
        candidates.add(f"{correct}_alt{i}")
        i += 1
    res = list(candidates)[:3]
    random.shuffle(res)
    return res


def wrap_text(text, font, max_width):
    words = text.split(" ")
    lines = []
    cur = ""
    for w in words:
        if font.size(cur + " " + w)[0] <= max_width:
            cur = (cur + " " + w).strip()
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


# ----------------------- Pygame Classes -----------------------
class Player(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.image = pygame.Surface((50, 20), pygame.SRCALPHA)
        pygame.draw.rect(self.image, (50, 200, 50), (0, 0, 50, 20), border_radius=4)
        self.rect = self.image.get_rect(center=(x, y))
        self.speed = PLAYER_SPEED

    def update(self, keys):
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.rect.x -= self.speed
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.rect.x += self.speed
        self.rect.x = max(0, min(self.rect.x, SCREEN_W - self.rect.width))


class Bullet(pygame.sprite.Sprite):
    def __init__(self, x, y, vx=0.0, vy=0.0):
        super().__init__()
        self.image = pygame.Surface((6, 12), pygame.SRCALPHA)
        pygame.draw.rect(self.image, (255, 255, 0), (0, 0, 6, 12))
        self.rect = self.image.get_rect(center=(x, y))
        # float positions for smooth movement
        self.posx = float(self.rect.centerx)
        self.posy = float(self.rect.centery)
        self.vx = float(vx)
        self.vy = float(vy)
        self.target = None

    def update(self):
        self.posx += self.vx
        self.posy += self.vy
        self.rect.centerx = int(self.posx)
        self.rect.centery = int(self.posy)
        # kill if far out of bounds (with small margin)
        if (
            self.rect.bottom < -50
            or self.rect.top > SCREEN_H + 50
            or self.rect.left > SCREEN_W + 50
            or self.rect.right < -50
        ):
            self.kill()


class Enemy(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.image = pygame.Surface((40, 30))
        self.image.fill((200, 50, 50))
        self.rect = self.image.get_rect(topleft=(x, y))


# ----------------------- Main Game -----------------------
def main():
    pygame.init()
    try:
        pygame.mixer.init()
    except Exception:
        pass
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("Study Invaders - Trajectory v3")
    clock = pygame.time.Clock()
    font = pygame.font.Font(FONT_NAME, 18)
    bigfont = pygame.font.Font(FONT_NAME, 28)

    # load sounds (expected to be in same folder)
    base = Path(".")
    fire_snd = None
    hit_snd = None
    try:
        fire_snd = pygame.mixer.Sound(str(base / "fire.wav"))
    except Exception as e:
        print("Warning: couldn't load fire.wav:", e)
    try:
        hit_snd = pygame.mixer.Sound(str(base / "hit.wav"))
    except Exception as e:
        print("Warning: couldn't load hit.wav:", e)

    # Load questions
    data_path = Path(QUESTIONS_CSV)
    if not data_path.exists():
        print(f"Could not find {QUESTIONS_CSV} in current directory. Exiting.")
        pygame.quit()
        sys.exit(1)

    questions = load_questions(QUESTIONS_CSV)
    if not questions:
        print("No valid questions found in CSV. Exiting.")
        pygame.quit()
        sys.exit(1)
    random.shuffle(questions)
    answer_pool = [q["a"] for q in questions]

    # Sprites
    player = Player(SCREEN_W // 2, SCREEN_H - 40)
    player_group = pygame.sprite.Group(player)
    bullets = pygame.sprite.Group()
    enemies = pygame.sprite.Group()

    def spawn_enemies():
        enemies.empty()
        total_w = ENEMY_COLS * 40 + (ENEMY_COLS - 1) * ENEMY_PADDING
        start_x = (SCREEN_W - total_w) // 2
        for row in range(ENEMY_ROWS):
            for col in range(ENEMY_COLS):
                x = start_x + col * (40 + ENEMY_PADDING)
                y = 50 + row * (30 + ENEMY_PADDING)
                enemies.add(Enemy(x, y))

    spawn_enemies()
    enemy_dir = 1
    enemy_speed = 0.5
    score = 0
    lives = LIVES
    pending_target = None
    muzzle_timer = 0  # milliseconds for muzzle flash

    # Quiz state machine
    state = "asking"  # "asking", "playing", "game_over"
    current_q = None
    choices = []
    correct_choice_index = 0
    question_index = 0

    def load_next_question():
        nonlocal current_q, choices, correct_choice_index, question_index, state
        if question_index >= len(questions):
            question_index = 0
            random.shuffle(questions)
        current_q = questions[question_index]
        question_index += 1
        distractors = make_distractors(current_q["a"], answer_pool)
        choices = distractors + [current_q["a"]]
        random.shuffle(choices)
        correct_choice_index = choices.index(current_q["a"])
        state = "asking"

    load_next_question()

    # button layout for choices
    def choice_rects():
        w = 340
        h = 42
        gap = 12
        x = (SCREEN_W - w) // 2
        y0 = SCREEN_H // 2
        rects = []
        for i in range(4):
            r = pygame.Rect(x, y0 + i * (h + gap), w, h)
            rects.append(r)
        return rects

    # main loop
    running = True
    while running:
        dt = clock.tick(FPS)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if state == "asking":
                    mx, my = event.pos
                    rects = choice_rects()
                    for i, r in enumerate(rects):
                        if r.collidepoint(mx, my):
                            if i == correct_choice_index:
                                # fire: compute direction vector to target and normalize to BULLET_SPEED_MAG
                                if len(enemies.sprites()) > 0:
                                    # pick horizontal-closest enemy (looks sensible visually)
                                    target = min(
                                        enemies.sprites(),
                                        key=lambda e: abs(e.rect.centerx - player.rect.centerx),
                                    )
                                    start_x = player.rect.centerx
                                    start_y = player.rect.top
                                    dx = target.rect.centerx - start_x
                                    dy = target.rect.centery - start_y  # target is above so dy < 0
                                    dist = math.hypot(dx, dy)
                                    if dist <= 0.1:
                                        # fallback straight up
                                        vx = 0.0
                                        vy = -BULLET_SPEED_MAG
                                    else:
                                        # normalized direction vector scaled by bullet speed magnitude
                                        vx = (dx / dist) * BULLET_SPEED_MAG
                                        vy = (dy / dist) * BULLET_SPEED_MAG
                                    # create bullet with the computed (vx,vy)
                                    b = Bullet(start_x, start_y, vx=vx, vy=vy)
                                    b.target = target
                                    bullets.add(b)
                                    pending_target = target
                                    muzzle_timer = 160  # ms of muzzle flash
                                    state = "playing"
                                    # play fire sound
                                    if fire_snd:
                                        try:
                                            fire_snd.play()
                                        except:
                                            pass
                                else:
                                    score += 100
                                    if not enemies:
                                        spawn_enemies()
                                    load_next_question()
                                    state = "asking"
                            else:
                                lives -= 1
                                if lives <= 0:
                                    state = "game_over"
                                else:
                                    load_next_question()
                            break

        keys = pygame.key.get_pressed()
        if state == "playing":
            # update game (player, bullets, enemies) until bullet hits an enemy or time passes
            player.update(keys)
            bullets.update()
            enemies.update()

            # move enemies left-right and down occasionally
            # freeze enemy horizontal movement while a pending_target exists so the bullet won't miss
            if pending_target is None:
                move_x = enemy_dir * enemy_speed * dt
                for e in enemies:
                    e.rect.x += move_x
            else:
                # small vertical nudge (optional)
                for e in enemies:
                    e.rect.y += 0

            # if any enemy hits side and no pending target, flip direction and move down
            if enemies and pending_target is None:
                leftmost = min(e.rect.left for e in enemies)
                rightmost = max(e.rect.right for e in enemies)
                if leftmost <= 0 or rightmost >= SCREEN_W:
                    enemy_dir *= -1
                    for e in enemies:
                        e.rect.y += 10

            # normal collisions: bullet hits enemy
            hits = pygame.sprite.groupcollide(enemies, bullets, True, True)
            if hits:
                # award points for each enemy hit (usually one)
                score += 100 * len(hits)
                # play hit sound
                if hit_snd:
                    try:
                        hit_snd.play()
                    except:
                        pass
                # clear pending_target if it was among hits
                if pending_target is not None:
                    pending_target = None
                # after a successful hit, load next question and respawn if needed
                if not enemies:
                    spawn_enemies()
                load_next_question()

            # Forced hit: use distance threshold to confirm visually-close hit
            if pending_target is not None:
                for b in list(bullets):
                    if getattr(b, "target", None) is pending_target:
                        # compute distance between centers
                        dx = b.rect.centerx - pending_target.rect.centerx
                        dy = b.rect.centery - pending_target.rect.centery
                        dist = math.hypot(dx, dy)
                        # set a reasonable collision radius based on enemy size
                        collision_radius = max(14, (pending_target.rect.width + pending_target.rect.height) // 6)
                        if dist <= collision_radius:
                            try:
                                pending_target.kill()
                            except:
                                pass
                            b.kill()
                            score += 100
                            if hit_snd:
                                try:
                                    hit_snd.play()
                                except:
                                    pass
                            pending_target = None
                            if not enemies:
                                spawn_enemies()
                            load_next_question()
                            break

            # if no bullets and still playing, return to asking (so player can't stall)
            if len(bullets) == 0:
                state = "asking"

        elif state == "asking":
            player.update(keys)
            bullets.update()
            enemies.update()
            # normal enemy drift even during asking
            move_x = enemy_dir * enemy_speed * dt * 0.2
            for e in enemies:
                e.rect.x += move_x
            if enemies:
                leftmost = min(e.rect.left for e in enemies)
                rightmost = max(e.rect.right for e in enemies)
                if leftmost <= 0 or rightmost >= SCREEN_W:
                    enemy_dir *= -1
                    for e in enemies:
                        e.rect.y += 5

        # draw
        screen.fill((20, 20, 40))
        enemies.draw(screen)
        bullets.draw(screen)
        player_group.draw(screen)

        # muzzle flash drawing (if active)
        if muzzle_timer > 0:
            muzzle_timer -= dt
            mx = player.rect.centerx
            my = player.rect.top - 6
            pygame.draw.circle(screen, (255, 220, 80), (mx, my), 8)

        # HUD
        hud = font.render(f"Score: {score}   Lives: {lives}", True, (255, 255, 255))
        screen.blit(hud, (10, 10))

        # If asking, draw the question overlay and choices
        if state == "asking" and current_q:
            overlay = pygame.Surface((SCREEN_W - 60, SCREEN_H - 220))
            overlay.set_alpha(220)
            overlay.fill((30, 30, 60))
            ox = 30
            oy = 80
            screen.blit(overlay, (ox, oy))
            # question text (wrapped)
            qlines = wrap_text(current_q["q"], bigfont, SCREEN_W - 120)
            qy = oy + 12
            for line in qlines:
                textsurf = bigfont.render(line, True, (255, 255, 255))
                screen.blit(textsurf, (ox + 18, qy))
                qy += textsurf.get_height() + 4

            # draw choices as buttons
            rects = choice_rects()
            for i, r in enumerate(rects):
                pygame.draw.rect(screen, (80, 80, 120), r, border_radius=6)
                lines = wrap_text(choices[i], font, r.w - 16)
                ty = r.y + 6
                for ln in lines:
                    screen.blit(font.render(ln, True, (255, 255, 255)), (r.x + 8, ty))
                    ty += font.get_height() + 2

        elif state == "game_over":
            go = bigfont.render("GAME OVER", True, (255, 50, 50))
            screen.blit(go, (SCREEN_W // 2 - go.get_width() // 2, SCREEN_H // 2 - 40))
            hint = font.render(
                "Press R to restart or Q to quit.", True, (255, 255, 255)
            )
            screen.blit(
                hint, (SCREEN_W // 2 - hint.get_width() // 2, SCREEN_H // 2 + 10)
            )
            if keys[pygame.K_r]:
                lives = LIVES
                score = 0
                spawn_enemies()
                load_next_question()
                state = "asking"
            if keys[pygame.K_q]:
                running = False

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
