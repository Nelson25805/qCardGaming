"""
games/space_game.py (patched)
Shows additional HUD: remaining session time, per-question timer, and music status.
"""

import pygame, random, math, sys
from pathlib import Path
import quiz_loader
import utils

SCREEN_W, SCREEN_H = 800, 600
BULLET_SPEED_MAG = 12.0


def format_time_ms(ms):
    """Format milliseconds as M:SS. If ms is None, return the infinity symbol."""
    if ms is None:
        return "∞"
    if ms < 0:
        ms = 0
    s = int(ms // 1000)
    m = s // 60
    s = s % 60
    return f"{m}:{s:02d}"


class SpaceGame:
    def __init__(self, csv_path, screen=None, settings=None):
        self.csv_path = csv_path
        self.screen = screen  # optional external pygame surface
        self.settings = settings
        self.font_name = None
        # runtime state
        self.questions = []
        self.answer_pool = []
        self.player = None
        self.player_group = None
        self.bullets = None
        self.enemies = None
        self.enemy_dir = 1
        self.enemy_speed = 0.5
        self.score = 0
        self.lives = 3
        self.initial_lives = 3
        self.pending_target = None
        self.muzzle_timer = 0
        self.state = "asking"
        self.current_q = None
        self.choices = []
        self.correct_choice_index = 0
        self.question_index = 0
        # pygame resources
        self.fire_snd = None
        self.hit_snd = None

        # timers
        self.question_timer_ms = None
        self.session_time_ms = None
        self.session_elapsed_ms = 0
        # flags set from settings
        self.sfx_enabled = True
        self.music_enabled = False
        self.muzzle_flash = True

    # -- loading / setup --
    def load_questions(self):
        self.questions = quiz_loader.load_questions(self.csv_path)
        # apply question order based on settings (defaults handled by settings object)
        order = None
        if self.settings is not None:
            order = getattr(self.settings, "question_order", None)
        self.answer_pool = [q["a"] for q in self.questions]
        if order == "top":
            # keep original file order
            pass
        elif order == "bottom":
            self.questions.reverse()
        else:
            random.shuffle(self.questions)

    def setup_pygame_objects(self):
        # Sprites
        self.player = Player(SCREEN_W // 2, SCREEN_H - 40)
        self.player_group = pygame.sprite.Group(self.player)
        self.bullets = pygame.sprite.Group()
        self.enemies = pygame.sprite.Group()
        self.spawn_enemies()

    def spawn_enemies(self):
        self.enemies.empty()
        total_w = 6 * 40 + (6 - 1) * 10
        start_x = (SCREEN_W - total_w) // 2
        for row in range(3):
            for col in range(6):
                x = start_x + col * (40 + 10)
                y = 50 + row * (30 + 10)
                self.enemies.add(Enemy(x, y))

    # -- quiz helper --
    def load_next_question(self):
        if not self.questions:
            # no questions available — set safe defaults so UI can render and we don't crash
            self.current_q = None
            self.choices = []
            self.correct_choice_index = -1
            self.state = "asking"
            self.question_timer_ms = None
            return

        if self.question_index >= len(self.questions):
            self.question_index = 0
            random.shuffle(self.questions)
        self.current_q = self.questions[self.question_index]
        self.question_index += 1
        distractors = quiz_loader.make_distractors(
            self.current_q["a"], self.answer_pool
        )
        self.choices = distractors + [self.current_q["a"]]
        random.shuffle(self.choices)
        self.correct_choice_index = self.choices.index(self.current_q["a"])
        self.state = "asking"
        # reset per-question timer if configured
        if getattr(self, "time_between_questions_ms", None) is not None:
            self.question_timer_ms = int(self.time_between_questions_ms)
        else:
            self.question_timer_ms = None

    # -- sounds --
    def load_sounds(self, folder):
        base = Path(folder)
        try:
            self.fire_snd = pygame.mixer.Sound(str(base / "fire.wav"))
        except:
            self.fire_snd = None
        try:
            self.hit_snd = pygame.mixer.Sound(str(base / "hit.wav"))
        except:
            self.hit_snd = None

    # -- main run method --
    def run(self):
        pygame.init()
        try:
            pygame.mixer.init()
        except:
            pass
        screen = self.screen or pygame.display.set_mode((SCREEN_W, SCREEN_H))
        clock = pygame.time.Clock()
        font = pygame.font.Font(self.font_name, 18)
        bigfont = pygame.font.Font(self.font_name, 28)
        smallfont = pygame.font.Font(self.font_name, 14)

        # load questions and setup sprites
        self.load_questions()
        self.setup_pygame_objects()
        # apply settings defaults: lives, music, sfx, enemy speed multiplier, timers
        if self.settings is not None:
            if getattr(self.settings, "lives", None) is None:
                self.lives = 9999999  # effectively unlimited
            else:
                self.lives = int(self.settings.lives)
            self.initial_lives = self.lives
            # enemy speed multiplier
            self.enemy_speed = self.enemy_speed * float(
                getattr(self.settings, "enemy_speed_multiplier", 1.0)
            )
            # total session timer (seconds) -> convert to milliseconds counter
            total_time = getattr(self.settings, "total_time", None)
            if total_time is None:
                self.session_time_ms = None
            else:
                # if user set minutes, settings may already be seconds; we'll accept seconds here
                self.session_time_ms = int(total_time * 1000)
            # time between questions (stored in settings as seconds OR milliseconds; accept string/int/float)
            tbq = getattr(self.settings, "time_between_questions", None)
            if tbq is None:
                self.time_between_questions_ms = None
            else:
                # handle strings like "10", numbers like 10 (seconds), or already-milliseconds values
                try:
                    if isinstance(tbq, str):
                        tbq_val = float(tbq)
                    else:
                        tbq_val = float(tbq)
                except Exception:
                    tbq_val = None
                if tbq_val is None:
                    # fallback: treat as seconds parsed from string digits
                    try:
                        tbq_val = float(
                            "".join([c for c in str(tbq) if (c.isdigit() or c == ".")])
                        )
                    except Exception:
                        tbq_val = None
                if tbq_val is None:
                    self.time_between_questions_ms = None
                else:
                    # Heuristic: if value looks large (>1000) assume it's already milliseconds
                    if tbq_val > 1000:
                        self.time_between_questions_ms = int(tbq_val)
                    else:
                        # treat as seconds -> convert to ms
                        self.time_between_questions_ms = int(tbq_val * 1000)
            # sfx/music flags
            self.sfx_enabled = bool(getattr(self.settings, "sfx", True))
            self.music_enabled = bool(getattr(self.settings, "music", False))
            self.muzzle_flash = bool(getattr(self.settings, "muzzle_flash", True))
        else:
            self.session_time_ms = None
            self.time_between_questions_ms = None
            self.sfx_enabled = True
            self.music_enabled = False
            self.muzzle_flash = True

        self.load_next_question()
        # music
        if self.music_enabled and getattr(self.settings, "music_choice", ""):
            try:
                pygame.mixer.music.load(
                    str(Path(getattr(self.settings, "music_choice")))
                )
                pygame.mixer.music.play(-1)
            except Exception:
                pass
        # timers
        # Note: DO NOT overwrite question_timer_ms here — load_next_question() already sets it when needed.
        # Keep session timer reset, but preserve question_timer_ms so the first question countdown starts immediately.
        self.session_elapsed_ms = 0

        running = True
        while running:
            dt = clock.tick(60)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    return "quit"
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.state == "asking":
                        mx, my = event.pos
                        rects = utils.choice_rects(SCREEN_W, SCREEN_H)
                        for i, r in enumerate(rects):
                            if r.collidepoint(mx, my):
                                if i == self.correct_choice_index:
                                    if len(self.enemies.sprites()) > 0:
                                        target = min(
                                            self.enemies.sprites(),
                                            key=lambda e: abs(
                                                e.rect.centerx
                                                - self.player.rect.centerx
                                            ),
                                        )
                                        start_x = self.player.rect.centerx
                                        start_y = self.player.rect.top
                                        dx = target.rect.centerx - start_x
                                        dy = target.rect.centery - start_y
                                        dist = math.hypot(dx, dy)
                                        if dist <= 0.1:
                                            vx = 0.0
                                            vy = -BULLET_SPEED_MAG
                                        else:
                                            vx = (dx / dist) * BULLET_SPEED_MAG
                                            vy = (dy / dist) * BULLET_SPEED_MAG
                                        b = Bullet(start_x, start_y, vx=vx, vy=vy)
                                        b.target = target
                                        self.bullets.add(b)
                                        self.pending_target = target
                                        self.muzzle_timer = 160
                                        self.state = "playing"
                                        if self.fire_snd and self.sfx_enabled:
                                            try:
                                                self.fire_snd.play()
                                            except:
                                                pass
                                    else:
                                        self.score += 100
                                        if len(self.enemies) == 0:
                                            self.spawn_enemies()
                                        self.load_next_question()
                                        self.state = "asking"
                                else:
                                    # if unlimited lives, don't decrement below huge number
                                    if self.lives < 999999:
                                        self.lives -= 1
                                    if self.lives <= 0:
                                        self.state = "game_over"
                                    else:
                                        self.load_next_question()
                                break

            keys = pygame.key.get_pressed()

            # update session timer
            if getattr(self, "session_time_ms", None) is not None:
                self.session_elapsed_ms += dt
                if self.session_elapsed_ms >= self.session_time_ms:
                    # session time up -> game over
                    self.state = "game_over"

            # update question timer (only when asking)
            if (
                self.state == "asking"
                and getattr(self, "question_timer_ms", None) is not None
            ):
                self.question_timer_ms -= dt
                if self.question_timer_ms <= 0:
                    # time up for this question -> lose a life (unless lives unlimited)
                    if getattr(self, "lives", 0) < 999999:
                        self.lives -= 1
                    # advance question or end
                    if self.lives <= 0:
                        self.state = "game_over"
                    else:
                        # when question_mode is 'one_each', running out of questions ends session - otherwise continue
                        qmode = (
                            getattr(self.settings, "question_mode", "loop")
                            if getattr(self, "settings", None)
                            else "loop"
                        )
                        if qmode == "one_each" and self.question_index >= len(
                            self.questions
                        ):
                            self.state = "game_over"
                        else:
                            self.load_next_question()

            if self.state == "playing":
                self.player.update(keys)
                self.bullets.update()
                self.enemies.update()

                if self.pending_target is None:
                    move_x = self.enemy_dir * self.enemy_speed * dt
                    for e in self.enemies:
                        e.rect.x += move_x

                if self.enemies and self.pending_target is None:
                    leftmost = min(e.rect.left for e in self.enemies)
                    rightmost = max(e.rect.right for e in self.enemies)
                    if leftmost <= 0 or rightmost >= SCREEN_W:
                        self.enemy_dir *= -1
                        for e in self.enemies:
                            e.rect.y += 10

                hits = pygame.sprite.groupcollide(
                    self.enemies, self.bullets, True, True
                )
                if hits:
                    self.score += 100 * len(hits)
                    if self.hit_snd and self.sfx_enabled:
                        try:
                            self.hit_snd.play()
                        except:
                            pass
                    if self.pending_target is not None:
                        self.pending_target = None
                    if len(self.enemies) == 0:
                        self.spawn_enemies()
                    self.load_next_question()

                # forced hit via proximity
                if self.pending_target is not None:
                    for b in list(self.bullets):
                        if getattr(b, "target", None) is self.pending_target:
                            dx = b.posx - self.pending_target.rect.centerx
                            dy = b.posy - self.pending_target.rect.centery
                            dist = math.hypot(dx, dy)
                            collision_radius = max(
                                14,
                                (
                                    self.pending_target.rect.width
                                    + self.pending_target.rect.height
                                )
                                // 6,
                            )
                            if dist <= collision_radius:
                                try:
                                    self.pending_target.kill()
                                except:
                                    pass
                                b.kill()
                                self.score += 100
                                if self.hit_snd and self.sfx_enabled:
                                    try:
                                        self.hit_snd.play()
                                    except:
                                        pass
                                self.pending_target = None
                                if len(self.enemies) == 0:
                                    self.spawn_enemies()
                                self.load_next_question()
                                break

                if len(self.bullets) == 0:
                    self.state = "asking"

            elif self.state == "asking":
                self.player.update(keys)
                self.bullets.update()
                self.enemies.update()
                move_x = self.enemy_dir * self.enemy_speed * dt * 0.2
                for e in self.enemies:
                    e.rect.x += move_x
                if self.enemies:
                    leftmost = min(e.rect.left for e in self.enemies)
                    rightmost = max(e.rect.right for e in self.enemies)
                    if leftmost <= 0 or rightmost >= SCREEN_W:
                        self.enemy_dir *= -1
                        for e in self.enemies:
                            e.rect.y += 5

            # draw
            screen.fill((20, 20, 40))
            self.enemies.draw(screen)
            self.bullets.draw(screen)
            self.player_group.draw(screen)

            if self.muzzle_timer > 0 and self.muzzle_flash:
                self.muzzle_timer -= dt
                mx = self.player.rect.centerx
                my = self.player.rect.top - 6
                pygame.draw.circle(screen, (255, 220, 80), (mx, my), 8)

            # HUD - top-left (score,lives) already present; add timers/music to top-right
            hud = font.render(
                f"Score: {self.score}   Lives: {self.lives}", True, (255, 255, 255)
            )
            screen.blit(hud, (10, 10))

            # build status strings for top-right
            # session remaining
            if getattr(self, "session_time_ms", None) is not None:
                remaining = max(0, int(self.session_time_ms - self.session_elapsed_ms))
                session_str = f"Session: {format_time_ms(remaining)}"
            else:
                session_str = "Session: ∞"

            # question timer remaining
            if getattr(self, "question_timer_ms", None) is not None:
                qstr = f"Q time: {format_time_ms(self.question_timer_ms)}"
            else:
                qstr = "Q time: ∞"

            # music status
            music_label = "Music: Off"
            if getattr(self, "music_enabled", False):
                mc = (
                    getattr(self.settings, "music_choice", "")
                    if getattr(self, "settings", None)
                    else ""
                )
                if mc:
                    music_label = f"Music: On ({Path(mc).name})"
                else:
                    music_label = "Music: On (none)"

            # render the right-side HUD
            sx = SCREEN_W - 10
            right1 = smallfont.render(session_str, True, (200, 200, 255))
            right2 = smallfont.render(qstr, True, (200, 200, 255))
            right3 = smallfont.render(music_label, True, (200, 200, 255))
            # right-align them
            screen.blit(right1, (sx - right1.get_width(), 8))
            screen.blit(right2, (sx - right2.get_width(), 8 + right1.get_height() + 2))
            screen.blit(
                right3,
                (
                    sx - right3.get_width(),
                    8 + right1.get_height() + right2.get_height() + 6,
                ),
            )

            if self.state == "asking" and self.current_q:
                overlay = pygame.Surface((SCREEN_W - 60, SCREEN_H - 220))
                overlay.set_alpha(220)
                overlay.fill((30, 30, 60))
                ox = 30
                oy = 80
                screen.blit(overlay, (ox, oy))
                qlines = utils.wrap_text(self.current_q["q"], bigfont, SCREEN_W - 120)
                qy = oy + 12
                for line in qlines:
                    textsurf = bigfont.render(line, True, (255, 255, 255))
                    screen.blit(textsurf, (ox + 18, qy))
                    qy += textsurf.get_height() + 4
                rects = utils.choice_rects(SCREEN_W, SCREEN_H)
                for i, r in enumerate(rects):
                    pygame.draw.rect(screen, (80, 80, 120), r, border_radius=6)
                    lines = utils.wrap_text(self.choices[i], font, r.w - 16)
                    ty = r.y + 6
                    for ln in lines:
                        screen.blit(
                            font.render(ln, True, (255, 255, 255)), (r.x + 8, ty)
                        )
                        ty += font.get_height() + 2

            elif self.state == "game_over":
                go = bigfont.render("GAME OVER", True, (255, 50, 50))
                screen.blit(
                    go, (SCREEN_W // 2 - go.get_width() // 2, SCREEN_H // 2 - 40)
                )
                hint = font.render(
                    "Press R to restart or Q to quit.", True, (255, 255, 255)
                )
                screen.blit(
                    hint, (SCREEN_W // 2 - hint.get_width() // 2, SCREEN_H // 2 + 10)
                )
                keys = pygame.key.get_pressed()
                if keys[pygame.K_r]:
                    # restart using settings defaults
                    if getattr(self.settings, "lives", None) is None:
                        self.lives = 9999999
                    else:
                        self.lives = int(getattr(self.settings, "lives", 3))
                    self.initial_lives = self.lives
                    self.score = 0
                    self.spawn_enemies()
                    self.session_elapsed_ms = 0
                    self.load_next_question()
                    self.state = "asking"
                if keys[pygame.K_q]:
                    running = False
                    return "quit"

            pygame.display.flip()

        pygame.quit()


# --- Sprite classes used by the SpaceGame ---
class Player(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.image = pygame.Surface((50, 20), pygame.SRCALPHA)
        pygame.draw.rect(self.image, (50, 200, 50), (0, 0, 50, 20), border_radius=4)
        self.rect = self.image.get_rect(center=(x, y))
        self.speed = 6

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
