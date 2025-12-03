from pathlib import Path
import pygame, random, math
from .helpers import SCREEN_W, SCREEN_H
from . import sprites, resources
import quiz_loader, utils

MAX_BOTTLES_PER_WAVE = 24


class CowboyGame:
    def __init__(self, csv_path, screen=None, settings=None):
        self.csv_path = csv_path
        self.screen = screen
        self.settings = settings
        self.questions = []
        self.answer_pool = []
        self.sfx_bank = {}
        self.snd_shot = None
        self.snd_break = None
        self.snd_jam = None
        self.graphics = {
            "player": None,
            "bullet": None,
            "bottle_frames": [],
            "background": None,
        }
        self.player = None
        self.player_group = None
        self.bullets = None
        self.bottles = None
        self.score = 0
        self.lives = 3
        self.state = "asking"
        self.current_q = None
        self.choices = []
        self.correct_choice_index = -1
        self.question_index = 0

        # When True, finish advancing the run only after the targeted bottle's
        # break animation completes (used when the last question in one_each mode
        # is answered correctly and we want to show the break animation first).
        self.finish_after_hit = False

        # flags from settings (defaults)
        self.sfx_enabled = True
        self.music_enabled = False

    def load_questions(self):
        # Read questions and build answer_pool, then apply ordering from settings
        self.questions = quiz_loader.load_questions(self.csv_path)
        self.answer_pool = [q["a"] for q in self.questions]
        order = None
        if self.settings is not None:
            order = getattr(self.settings, "question_order", None)
        if order == "top":
            # keep original file order
            pass
        elif order == "bottom":
            self.questions.reverse()
        else:
            # default/random
            random.shuffle(self.questions)

    def load_sounds(self, folder=None):
        resources.load_sounds(self, folder)

    def load_graphics(self, folder=None):
        # resources.load_graphics will fill 'player','bullet','bottle_frames' and possibly 'background'
        resources.load_graphics(self, folder)

    def spawn_bottles(self, count=None):
        """Spawn `count` bottles into rows/cols (cols=8). Each bottle keeps frames for animation."""
        if count is None:
            count = MAX_BOTTLES_PER_WAVE
        self.bottles.empty()
        cols = 8
        rows = (count + cols - 1) // cols
        total_w = cols * 28  # spacing approximate (width per bottle grid)
        start_x = (SCREEN_W - total_w) // 2 + 14
        start_y = 120
        placed = 0
        frames = self.graphics.get("bottle_frames", []) or []
        for r in range(rows):
            for c in range(cols):
                if placed >= count:
                    break
                x = start_x + c * 28
                y = start_y + r * 48
                b = sprites.Bottle(x, y, frames)
                self.bottles.add(b)
                placed += 1

    def spawn_bottles_for_mode_initial(self):
        """Decide how many bottles to spawn based on settings.question_mode and remaining questions."""
        qmode = (
            getattr(self.settings, "question_mode", "loop")
            if getattr(self, "settings", None)
            else "loop"
        )
        if qmode == "one_each":
            total_questions = len(self.questions)
            # remaining questions = total - (question_index - 1)
            remaining = max(0, total_questions - max(0, self.question_index - 1))
            spawn_count = min(MAX_BOTTLES_PER_WAVE, max(0, remaining))
            if spawn_count > 0:
                self.spawn_bottles(spawn_count)
            else:
                self.bottles.empty()
        else:
            self.spawn_bottles(MAX_BOTTLES_PER_WAVE)

    def setup_objects(self):
        self.player = sprites.Player(
            SCREEN_W // 2, SCREEN_H - 24, image=self.graphics.get("player")
        )
        self.player_group = pygame.sprite.Group(self.player)
        self.bullets = pygame.sprite.Group()
        self.bottles = pygame.sprite.Group()
        # spawn bottles based on mode and question count
        self.spawn_bottles_for_mode_initial()

    def load_next_question(self):
        if not self.questions:
            self.current_q = None
            self.choices = []
            self.correct_choice_index = -1
            self.state = "asking"
            return

        # if we're at/after the end and question_mode is one_each -> finish
        if self.question_index >= len(self.questions):
            if getattr(self.settings, "question_mode", "loop") == "one_each":
                self.current_q = None
                self.choices = []
                self.correct_choice_index = -1
                # decide win/lose based on remaining lives
                if (self.lives is None) or (
                    isinstance(self.lives, int) and self.lives > 0
                ):
                    self.state = "won"
                else:
                    self.state = "game_over"
                return
            else:
                # loop mode -> reshuffle and reset index
                self.question_index = 0
                random.shuffle(self.questions)

        # normal case
        self.current_q = self.questions[self.question_index]
        # increment question_index to indicate we've prepared this question
        self.question_index += 1

        distractors = quiz_loader.make_distractors(
            self.current_q["a"], self.answer_pool
        )
        self.choices = distractors + [self.current_q["a"]]
        random.shuffle(self.choices)
        self.correct_choice_index = self.choices.index(self.current_q["a"])
        self.state = "asking"

    def run(self):
        pygame.init()
        try:
            pygame.mixer.init()
        except:
            pass
        screen = self.screen or pygame.display.set_mode((SCREEN_W, SCREEN_H))
        clock = pygame.time.Clock()
        font = pygame.font.Font(None, 18)
        bigfont = pygame.font.Font(None, 24)

        # load questions and prepare the first question
        self.load_questions()
        self.load_next_question()

        # load graphics & sounds from package assets first (fall back if needed)
        try:
            self.load_graphics(Path("games") / "cowboy_shooter" / "assets" / "Graphics")
        except:
            try:
                self.load_graphics()
            except:
                pass

        self.setup_objects()

        # apply settings
        if self.settings is not None:
            if getattr(self.settings, "lives", None) is None:
                self.lives = None
            else:
                self.lives = int(self.settings.lives)
            self.sfx_enabled = bool(getattr(self.settings, "sfx", True))
            self.music_enabled = bool(getattr(self.settings, "music", False))

        try:
            self.load_sounds(
                Path("games") / "cowboy_shooter" / "assets" / "Sound Effects"
            )
        except:
            try:
                self.load_sounds()
            except:
                pass

        # friendly sfx attrs
        self.snd_shot = self.sfx_bank.get("shot")
        self.snd_break = self.sfx_bank.get("break")
        self.snd_jam = self.sfx_bank.get("jam")

        # music start (prefer per-game music, then global)
        if self.music_enabled:
            mc = getattr(self.settings, "music_choice", "") or ""
            mus_candidates = [
                Path("games") / "cowboy_shooter" / "assets" / "Music" / mc,
                Path("assets") / "music" / mc,
                Path(mc),
            ]
            for p in mus_candidates:
                if p.exists() and p.is_file():
                    try:
                        pygame.mixer.music.load(str(p))
                        pygame.mixer.music.play(-1)
                        break
                    except:
                        pass

        # overlay geometry defaults (width and padding) — height computed dynamically
        OVERLAY_W = SCREEN_W - 200
        CHOICE_H = 40
        CHOICE_GAP = 8
        CHOICE_PAD_X = 16
        TOP_PAD = 12
        BOTTOM_PAD = 12
        MAX_OVERLAY_H = SCREEN_H - 120

        def compute_overlay_layout():
            """
            Returns: overlay_rect, qlines (list of strings), choice_rects (list of pygame.Rect)
            The overlay height is computed based on question text and how many choices there are.
            """
            max_text_w = OVERLAY_W - 2 * CHOICE_PAD_X
            qlines = (
                utils.wrap_text(self.current_q["q"], bigfont, max_text_w)
                if self.current_q
                else []
            )
            q_line_h = bigfont.get_height()
            q_text_height = len(qlines) * (q_line_h + 4)

            choices_total_h = len(self.choices) * CHOICE_H + max(
                0, (len(self.choices) - 1) * CHOICE_GAP
            )

            overlay_h = TOP_PAD + q_text_height + 8 + choices_total_h + BOTTOM_PAD
            overlay_h = min(overlay_h, MAX_OVERLAY_H)

            overlay_x = (SCREEN_W - OVERLAY_W) // 2
            overlay_y = SCREEN_H - overlay_h - 40  # anchored near bottom

            overlay_rect = pygame.Rect(overlay_x, overlay_y, OVERLAY_W, overlay_h)

            # compute choice rect positions inside overlay
            choices_start_y = overlay_rect.y + TOP_PAD + q_text_height + 8
            rects = []
            for i in range(len(self.choices)):
                rx = overlay_rect.x + CHOICE_PAD_X
                ry = choices_start_y + i * (CHOICE_H + CHOICE_GAP)
                r = pygame.Rect(rx, ry, OVERLAY_W - 2 * CHOICE_PAD_X, CHOICE_H)
                rects.append(r)
            return overlay_rect, qlines, rects

        running = True
        while running:
            dt = clock.tick(60)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    try:
                        pygame.mixer.music.stop()
                    except:
                        pass
                    running = False
                    return "quit"
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.state == "asking" and self.current_q:
                        mx, my = event.pos
                        # compute the same overlay/choice rects used when drawing
                        overlay_rect, qlines, rects = compute_overlay_layout()
                        for i, r in enumerate(rects[: len(self.choices)]):
                            if r.collidepoint(mx, my):
                                if i == self.correct_choice_index:
                                    # correct answer
                                    if len(self.bottles.sprites()) > 0:
                                        # find target bottle closest to player's aim
                                        target = min(
                                            self.bottles.sprites(),
                                            key=lambda b: abs(
                                                b.rect.centerx - self.player.aim_x
                                            ),
                                        )
                                        start_x = self.player.rect.centerx
                                        start_y = self.player.rect.top - 10
                                        dx = target.rect.centerx - start_x
                                        dy = target.rect.centery - start_y
                                        dist = math.hypot(dx, dy)
                                        if dist <= 0.1:
                                            vx = 0.0
                                            vy = -10.0
                                        else:
                                            vx = (dx / dist) * 10.0
                                            vy = (dy / dist) * 10.0
                                        bl = sprites.Bullet(
                                            start_x,
                                            start_y,
                                            vx=vx,
                                            vy=vy,
                                            image=self.graphics.get("bullet"),
                                        )
                                        self.bullets.add(bl)
                                        if self.snd_shot and self.sfx_enabled:
                                            try:
                                                self.snd_shot.play()
                                            except:
                                                pass

                                        # Determine if this is the last question in one_each mode.
                                        last_q_and_one_each = getattr(
                                            self.settings, "question_mode", "loop"
                                        ) == "one_each" and self.question_index >= len(
                                            self.questions
                                        )

                                        if last_q_and_one_each:
                                            # finish after the hit animation
                                            self.finish_after_hit = True
                                            # DO NOT advance the question now — wait for the hit
                                            self.state = "playing"
                                        else:
                                            # advance question now so UI updates immediately
                                            self.load_next_question()
                                            # if loading next question finished the run, stop music if needed
                                            if self.state in ("won", "game_over"):
                                                try:
                                                    pygame.mixer.music.stop()
                                                except:
                                                    pass
                                            else:
                                                self.state = "playing"
                                    else:
                                        # no bottles (edge-case) -> award points and advance
                                        self.score += 100
                                        self.load_next_question()
                                else:
                                    # incorrect -> jam, lose life if finite, advance question
                                    if self.snd_jam and self.sfx_enabled:
                                        try:
                                            self.snd_jam.play()
                                        except:
                                            pass
                                    if self.lives is not None:
                                        self.lives -= 1
                                    # check game over
                                    if self.lives is not None and self.lives <= 0:
                                        self.state = "game_over"
                                        try:
                                            pygame.mixer.music.stop()
                                        except:
                                            pass
                                    else:
                                        # advance question regardless of correctness (do not repeat)
                                        self.load_next_question()
                                break

            # input & updates
            keys = pygame.key.get_pressed()
            self.player.update(keys)
            self.bullets.update()

            # collision: bullets vs bottles
            for b in list(self.bullets):
                hits = pygame.sprite.spritecollide(b, self.bottles, dokill=False)
                if hits:
                    for hit in hits:
                        hit.start_break()
                        b.kill()
                        if self.snd_break and self.sfx_enabled:
                            try:
                                self.snd_break.play()
                            except:
                                pass
                        self.score += 100
                    # After registering hit(s), clear state appropriately:
                    # If we were waiting to finish after a hit (final-question correct),
                    # now advance the question/run.
                    if self.finish_after_hit:
                        self.load_next_question()
                        if self.state in ("won", "game_over"):
                            try:
                                pygame.mixer.music.stop()
                            except:
                                pass
                        self.finish_after_hit = False

                    # set state back to asking (choices overlay) if not ended
                    if self.state not in ("won", "game_over"):
                        self.state = "asking"

            # update bottle animations (they call kill() when their break animation completes)
            for bottle in list(self.bottles):
                bottle.update(dt)

            # If all bottles cleared, prepare next wave (or finish run)
            if len(self.bottles) == 0 and self.state not in ("game_over", "won"):
                # prepare next question first (this may set state to won/game_over)
                self.load_next_question()

                if self.state in ("won", "game_over"):
                    try:
                        pygame.mixer.music.stop()
                    except:
                        pass
                else:
                    # spawn next wave based on mode & remaining questions
                    if getattr(self.settings, "question_mode", "loop") == "one_each":
                        total_questions = len(self.questions)
                        remaining = max(
                            0, total_questions - max(0, self.question_index - 1)
                        )
                        if remaining > 0:
                            self.spawn_bottles(min(MAX_BOTTLES_PER_WAVE, remaining))
                        else:
                            # no remaining -> keep bottles empty (load_next_question would have set win)
                            pass
                    else:
                        # loop mode: always spawn full wave
                        self.spawn_bottles(MAX_BOTTLES_PER_WAVE)
                    # go back to asking
                    if self.state not in ("game_over", "won"):
                        self.state = "asking"

            # draw
            screen.fill((60, 50, 30))
            wall_rect = pygame.Rect(60, 80, SCREEN_W - 120, 240)

            # draw shelf/background: prefer explicit background image if available
            bg = self.graphics.get("background")
            if bg:
                try:
                    bg_scaled = pygame.transform.smoothscale(
                        bg, (wall_rect.w, wall_rect.h)
                    )
                    screen.blit(bg_scaled, (wall_rect.x, wall_rect.y))
                except Exception:
                    pygame.draw.rect(screen, (90, 70, 50), wall_rect)
            else:
                # wood plank look
                plank_h = max(24, wall_rect.h // 4)
                for i in range(4):
                    py = wall_rect.y + i * plank_h
                    ph = (
                        plank_h
                        if (py + plank_h) <= wall_rect.bottom
                        else (wall_rect.bottom - py)
                    )
                    r = pygame.Rect(wall_rect.x, py, wall_rect.w, ph)
                    color = (110, 85, 50) if i % 2 == 0 else (100, 75, 45)
                    pygame.draw.rect(screen, color, r)
                    # subtle grain lines
                    for gx in range(r.x + 8, r.x + r.w - 8, 24):
                        pygame.draw.line(
                            screen,
                            (80, 60, 30),
                            (gx, r.y + 2),
                            (gx + 6, r.y + ph - 4),
                            1,
                        )
                # shelf ledge
                ledge = pygame.Rect(
                    wall_rect.x - 8, wall_rect.bottom - 10, wall_rect.w + 16, 12
                )
                pygame.draw.rect(screen, (70, 50, 30), ledge)
                pygame.draw.line(
                    screen,
                    (40, 30, 20),
                    (ledge.x, ledge.y),
                    (ledge.x + ledge.w, ledge.y),
                    2,
                )

            self.bottles.draw(screen)
            self.player_group.draw(screen)
            self.bullets.draw(screen)

            lives_display = "∞" if self.lives is None else str(self.lives)
            hud = font.render(
                f"Score: {self.score}   Lives: {lives_display}", True, (255, 255, 255)
            )
            screen.blit(hud, (10, 10))

            # draw question overlay with dynamic height so it fully covers Q + choices
            if self.state == "asking" and self.current_q:
                overlay_rect, qlines, rects = compute_overlay_layout()
                overlay = pygame.Surface(
                    (overlay_rect.w, overlay_rect.h), flags=pygame.SRCALPHA
                )
                # use per-pixel alpha to ensure overlay fully covers the area
                overlay.fill((28, 28, 40, 200))
                screen.blit(overlay, (overlay_rect.x, overlay_rect.y))

                # render question lines at top of overlay
                qy = overlay_rect.y + TOP_PAD
                for line in qlines:
                    textsurf = bigfont.render(line, True, (255, 255, 255))
                    screen.blit(textsurf, (overlay_rect.x + CHOICE_PAD_X, qy))
                    qy += textsurf.get_height() + 4

                # render choice rects inside overlay
                for i, r in enumerate(rects[: len(self.choices)]):
                    pygame.draw.rect(screen, (80, 80, 120), r, border_radius=6)
                    lines = utils.wrap_text(self.choices[i], font, r.w - 16)
                    ty = r.y + 6
                    for ln in lines:
                        screen.blit(
                            font.render(ln, True, (255, 255, 255)), (r.x + 8, ty)
                        )
                        ty += font.get_height() + 2

            elif self.state in ("game_over", "won"):
                if self.state == "won":
                    headline = bigfont.render("YOU WIN!", True, (80, 220, 120))
                else:
                    headline = bigfont.render("GAME OVER", True, (255, 50, 50))
                screen.blit(
                    headline,
                    (SCREEN_W // 2 - headline.get_width() // 2, SCREEN_H // 2 - 40),
                )
                details = font.render(f"Score: {self.score}", True, (200, 200, 200))
                screen.blit(
                    details, (SCREEN_W // 2 - details.get_width() // 2, SCREEN_H // 2)
                )
                hint = font.render(
                    "Press R to restart or Q to quit.", True, (255, 255, 255)
                )
                screen.blit(
                    hint, (SCREEN_W // 2 - hint.get_width() // 2, SCREEN_H // 2 + 30)
                )
                keys = pygame.key.get_pressed()
                if keys[pygame.K_r]:
                    if getattr(self.settings, "lives", None) is None:
                        self.lives = None
                    else:
                        self.lives = int(getattr(self.settings, "lives", 3))
                    self.score = 0
                    self.load_questions()
                    self.question_index = 0
                    self.load_next_question()
                    self.setup_objects()
                    self.state = "asking"
                    if self.music_enabled:
                        try:
                            pygame.mixer.music.play(-1)
                        except:
                            pass
                if keys[pygame.K_q]:
                    try:
                        pygame.mixer.music.stop()
                    except:
                        pass
                    running = False
                    return "quit"

            pygame.display.flip()

        try:
            pygame.mixer.music.stop()
        except:
            pass
        pygame.quit()
