# games/tower_defense/game.py
from pathlib import Path
import pygame
import random
import math
from .helpers import SCREEN_W, SCREEN_H
from . import sprites, resources
import quiz_loader, utils

MAX_TOWERS = 8


class TowerDefenseGame:
    """
    Tower defense study game:
      - one enemy spawns per question
      - correct answer -> nearest tower shoots and kills enemy
      - wrong answer or timeout -> enemy rushes to goal and damages power source
        (life lost only when enemy actually reaches the power source)
    """

    def __init__(self, csv_path, screen=None, settings=None):
        self.csv_path = csv_path
        self.screen = screen
        self.settings = settings

        # quiz state
        self.questions = []
        self.answer_pool = []
        self.question_index = 0
        self.current_q = None
        self.choices = []
        self.correct_choice_index = -1

        # graphics & sfx containers (resources.load_graphics / load_sounds fills these)
        self.graphics = {
            "course": None,
            "tower": None,
            "creature": None,
            "projectile": None,
        }
        self.sfx_bank = {}
        self.snd_shoot = None
        self.snd_hit = None
        self.snd_rush = None

        # sprite groups
        self.towers = pygame.sprite.Group()
        self.enemies = pygame.sprite.Group()
        self.projectiles = pygame.sprite.Group()

        # gameplay
        self.score = 0
        self.lives = 3
        self.state = (
            "asking"  # asking, playing (projectile/enemy active), game_over, won
        )
        self.finish_after_hit = False

        # timers (ms)
        self.session_time_ms = None
        self.session_elapsed_ms = 0
        self.question_timer_ms = None
        self.question_timer_start = None

        # flags
        self.sfx_enabled = True
        self.music_enabled = False

        # path and spawn/goal
        self.path = []
        self.spawn_pos = None
        self.goal_pos = None

    # ---------------- quiz helpers ----------------
    def load_questions(self):
        self.questions = quiz_loader.load_questions(self.csv_path)
        self.answer_pool = [q["a"] for q in self.questions]
        order = None
        if self.settings is not None:
            order = getattr(self.settings, "question_order", None)
        if order == "top":
            pass
        elif order == "bottom":
            self.questions.reverse()
        else:
            random.shuffle(self.questions)

    def load_next_question(self):
        """
        Prepare the next question, start its question timer (only if set),
        and spawn a single enemy.
        """
        if not self.questions:
            self.current_q = None
            self.choices = []
            self.correct_choice_index = -1
            self.state = "asking"
            return

        # finish condition if one_each mode
        if self.question_index >= len(self.questions):
            if getattr(self.settings, "question_mode", "loop") == "one_each":
                self.current_q = None
                self.choices = []
                self.correct_choice_index = -1
                if (self.lives is None) or (
                    isinstance(self.lives, int) and self.lives > 0
                ):
                    self.state = "won"
                else:
                    self.state = "game_over"
                return
            else:
                self.question_index = 0
                random.shuffle(self.questions)

        # load question
        self.current_q = self.questions[self.question_index]
        self.question_index += 1

        distractors = quiz_loader.make_distractors(
            self.current_q["a"], self.answer_pool
        )
        self.choices = distractors + [self.current_q["a"]]
        random.shuffle(self.choices)
        self.correct_choice_index = self.choices.index(self.current_q["a"])

        # question timer (ms) — only record a start time if timer exists
        tbq = getattr(self.settings, "time_between_questions", None)
        if tbq is None:
            self.question_timer_ms = None
            self.question_timer_start = None
        else:
            # settings store seconds; convert to ms
            self.question_timer_ms = int(tbq * 1000)
            self.question_timer_start = pygame.time.get_ticks()

        # spawn exactly one enemy for this question
        self.spawn_enemy_for_question()

        # set state to asking (overlay visible)
        self.state = "asking"

    # ---------------- resources ----------------
    def load_graphics(self, folder=None):
        resources.load_graphics(self, folder)

    def load_sounds(self, folder=None):
        resources.load_sounds(self, folder)

    # ---------------- path / towers / enemies ----------------
    def build_looped_path(self):
        """
        Build a smooth loop path (list of (x,y)) sized to the screen.
        Path is arranged so index 0 == spawn (left) and index ~half == goal (right).
        """
        cx = SCREEN_W // 2
        cy = SCREEN_H // 2 - 20
        rx = SCREEN_W * 0.32
        ry = SCREEN_H * 0.20
        pts = []
        steps = 240
        for i in range(steps):
            a = 2 * math.pi * i / steps
            x = cx + math.cos(a) * rx
            y = cy + math.sin(a) * ry + math.sin(2 * a) * 18
            pts.append((x, y))

        # define spawn around left (angle ~pi) and goal at right (angle ~0)
        spawn_idx = steps // 2
        goal_idx = 0
        self.spawn_pos = pts[spawn_idx]
        self.goal_pos = pts[goal_idx]
        # rotate list so path[0] == spawn and it moves forward toward goal
        self.path = pts[spawn_idx:] + pts[:spawn_idx]
        return self.path

    def place_towers_along_path(self, count=MAX_TOWERS):
        """
        Place towers at roughly-even intervals around the path, offset outside the track.
        """
        self.towers.empty()
        if not self.path:
            return
        n = max(1, count)
        L = len(self.path)
        step = max(1, L // n)
        for i in range(0, n * step, step):
            idx = i % L
            p0 = self.path[idx]
            p1 = self.path[(idx + 6) % L]
            dx = p1[0] - p0[0]
            dy = p1[1] - p0[1]
            dist = math.hypot(dx, dy) or 1.0
            nx = -dy / dist
            ny = dx / dist
            offset = 60 + random.uniform(-16, 16)
            tx = p0[0] + nx * offset
            ty = p0[1] + ny * offset
            t_surf = self.graphics.get("tower")
            tw = sprites.Tower(int(tx), int(ty), image=t_surf)
            self.towers.add(tw)

    def spawn_enemy_for_question(self):
        """
        Spawn exactly one enemy at spawn_pos and add to group.
        Enemy object expects to follow `self.path`.
        Initialize rush/loop flags so default behaviour is to loop until
        the player answers or a timeout/wrong answer forces a rush.
        """
        if not self.path:
            self.build_looped_path()
        multiplier = (
            getattr(self.settings, "enemy_speed_multiplier", 1.0)
            if self.settings
            else 1.0
        )
        base_speed = 60.0
        speed = base_speed * float(multiplier)
        eimg = self.graphics.get("creature")
        enemy = sprites.Enemy(self.path, speed=speed, image=eimg)
        # ensure enemy position is set to spawn (path[0] == spawn)
        enemy.pos = [float(self.spawn_pos[0]), float(self.spawn_pos[1])]
        enemy.rect.center = (int(enemy.pos[0]), int(enemy.pos[1]))
        enemy.goal_pos = self.goal_pos

        # Defensive initialisation: explicit state so enemy won't rush immediately.
        enemy.rush = False
        enemy.looping = True
        try:
            enemy.path_index = 0
        except Exception:
            pass

        self.enemies.add(enemy)
        # set state
        self.state = "asking"

    # ---------------- helpers ----------------
    def format_time_ms(self, ms):
        s = max(0, int(ms // 1000))
        m = s // 60
        s = s % 60
        return f"{m}:{s:02d}"

    # compute overlay layout used both for drawing and for click hit-testing
    def compute_overlay_layout(self, bigfont, font):
        OVERLAY_W = SCREEN_W - 200
        CHOICE_H = 40
        CHOICE_GAP = 8
        CHOICE_PAD_X = 16
        TOP_PAD = 12
        BOTTOM_PAD = 12
        MAX_OVERLAY_H = SCREEN_H - 120

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
        overlay_y = SCREEN_H - overlay_h - 30
        overlay_rect = pygame.Rect(overlay_x, overlay_y, OVERLAY_W, overlay_h)

        # compute rects
        choices_start_y = overlay_rect.y + TOP_PAD + q_text_height + 8
        rects = []
        for i in range(len(self.choices)):
            rx = overlay_rect.x + CHOICE_PAD_X
            ry = choices_start_y + i * (CHOICE_H + CHOICE_GAP)
            rects.append(pygame.Rect(rx, ry, OVERLAY_W - 2 * CHOICE_PAD_X, CHOICE_H))
        return (
            overlay_rect,
            qlines,
            rects,
            {"TOP_PAD": TOP_PAD, "CHOICE_PAD_X": CHOICE_PAD_X},
        )

    # ---------------- main run ----------------
    def run(self):
        pygame.init()
        try:
            pygame.mixer.init()
        except:
            pass

        screen = self.screen or pygame.display.set_mode((SCREEN_W, SCREEN_H))
        clock = pygame.time.Clock()
        font = pygame.font.Font(None, 18)
        smallfont = pygame.font.Font(None, 14)
        bigfont = pygame.font.Font(None, 24)

        # load questions + prepare first
        self.load_questions()
        self.load_next_question()

        # load graphics & sounds (prefer package assets)
        try:
            self.load_graphics(Path("games") / "tower_defense" / "assets" / "Graphics")
        except:
            try:
                self.load_graphics()
            except:
                pass

        # build path and towers (towers count based on path length)
        self.build_looped_path()
        tower_count = min(MAX_TOWERS, max(4, int(len(self.path) // 40)))
        self.place_towers_along_path(count=tower_count)

        # sprite groups
        self.projectiles = pygame.sprite.Group()

        # apply settings
        if self.settings is not None:
            if getattr(self.settings, "lives", None) is None:
                self.lives = None
            else:
                self.lives = int(self.settings.lives)
            self.sfx_enabled = bool(getattr(self.settings, "sfx", True))
            self.music_enabled = bool(getattr(self.settings, "music", False))

        # load sounds (package first)
        try:
            self.load_sounds(
                Path("games") / "tower_defense" / "assets" / "Sound Effects"
            )
        except:
            try:
                self.load_sounds()
            except:
                pass

        # wire sfx aliases from sfx_bank
        self.snd_shoot = (
            self.sfx_bank.get("shoot")
            or self.sfx_bank.get("shot")
            or self.sfx_bank.get("fire")
        )
        self.snd_hit = (
            self.sfx_bank.get("hit")
            or self.sfx_bank.get("impact")
            or self.sfx_bank.get("break")
        )
        self.snd_rush = (
            self.sfx_bank.get("rush")
            or self.sfx_bank.get("dash")
            or self.sfx_bank.get("alarm")
        )

        # start music if enabled
        if self.music_enabled:
            mc = getattr(self.settings, "music_choice", "") or ""
            mus_candidates = [
                Path("games") / "tower_defense" / "assets" / "Music" / mc,
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

        # session time: settings.total_time is in seconds; store ms
        if getattr(self.settings, "total_time", None) is not None:
            self.session_time_ms = int(getattr(self.settings, "total_time") * 1000)
        else:
            self.session_time_ms = None
        self.session_elapsed_ms = 0

        # main loop
        running = True
        last_ticks = pygame.time.get_ticks()
        while running:
            now = pygame.time.get_ticks()
            dt_ms = now - last_ticks
            last_ticks = now
            dt = dt_ms / 1000.0

            # session countdown
            if self.session_time_ms is not None:
                self.session_elapsed_ms += dt_ms
                if self.session_elapsed_ms >= self.session_time_ms:
                    # session ended -> finish run
                    running = False
                    return "quit"

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    try:
                        pygame.mixer.music.stop()
                    except:
                        pass
                    running = False
                    return "quit"

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    # only handle clicks while asking and question present
                    if self.state == "asking" and self.current_q:
                        mx, my = event.pos
                        overlay_rect, qlines, rects, meta = self.compute_overlay_layout(
                            bigfont, font
                        )
                        for i, r in enumerate(rects[: len(self.choices)]):
                            if r.collidepoint(mx, my):
                                # clicked a choice
                                if i == self.correct_choice_index:
                                    # correct: nearest tower shoots the current enemy
                                    if (
                                        len(self.enemies.sprites()) > 0
                                        and len(self.towers.sprites()) > 0
                                    ):
                                        # find the single enemy (should be one)
                                        enemy = min(
                                            self.enemies.sprites(),
                                            key=lambda e: math.hypot(
                                                e.pos[0] - self.spawn_pos[0],
                                                e.pos[1] - self.spawn_pos[1],
                                            ),
                                        )
                                        # find nearest tower to enemy
                                        nearest = None
                                        nd = 1e9
                                        for t in self.towers:
                                            tpos = getattr(
                                                t,
                                                "pos",
                                                (t.rect.centerx, t.rect.centery),
                                            )
                                            d = math.hypot(
                                                tpos[0] - enemy.pos[0],
                                                tpos[1] - enemy.pos[1],
                                            )
                                            if d < nd:
                                                nd = d
                                                nearest = t
                                        if nearest:
                                            proj = nearest.shoot_at(
                                                enemy.pos,
                                                self.projectiles,
                                                image=self.graphics.get("projectile"),
                                            )
                                            if self.snd_shoot and self.sfx_enabled:
                                                try:
                                                    self.snd_shoot.play()
                                                except:
                                                    pass
                                            self.state = "playing"
                                            last_q_and_one_each = getattr(
                                                self.settings, "question_mode", "loop"
                                            ) == "one_each" and self.question_index >= len(
                                                self.questions
                                            )
                                            if last_q_and_one_each:
                                                self.finish_after_hit = True
                                            else:
                                                # advance question now so UI updates, the enemy will be killed when projectile hits
                                                self.load_next_question()
                                        else:
                                            # no towers: immediate kill
                                            for e in list(self.enemies):
                                                e.kill()
                                            self.score += 100
                                            self.load_next_question()
                                    else:
                                        # no enemies -> award and advance
                                        self.score += 100
                                        self.load_next_question()
                                else:
                                    # WRONG ANSWER:
                                    # --- DO NOT subtract life now ---
                                    # Instruct current enemies to rush along path toward goal (path-follow)
                                    for e in list(self.enemies):
                                        # use sprite helper to set rush along path toward goal waypoint
                                        if hasattr(e, "set_rush_to_goal"):
                                            e.set_rush_to_goal(self.goal_pos)
                                        else:
                                            e.rush = True
                                            e.goal_pos = self.goal_pos
                                    if self.snd_rush and self.sfx_enabled:
                                        try:
                                            self.snd_rush.play()
                                        except:
                                            pass
                                    # hide question overlay and let the enemy reach the goal.
                                    self.state = "playing"
                                    # DO NOT call load_next_question() here — wait until enemy reaches goal
                                break

            # update all sprites
            self.enemies.update(dt)
            self.projectiles.update(dt)

            # projectiles hitting enemies
            for proj in list(self.projectiles):
                hits = pygame.sprite.spritecollide(proj, self.enemies, dokill=False)
                if hits:
                    for e in hits:
                        e.kill()
                        self.score += 100
                        if self.snd_hit and self.sfx_enabled:
                            try:
                                self.snd_hit.play()
                            except:
                                pass
                    proj.kill()
                    if self.finish_after_hit:
                        self.finish_after_hit = False
                        self.load_next_question()
                    else:
                        if self.state not in ("game_over", "won"):
                            self.state = "asking"

            # enemies reach goal (only if the enemy is rushing along the path and actually reached waypoint)
            for e in list(self.enemies):
                # only treat as reaching the goal if the enemy is rushing toward it
                if not getattr(e, "rush", False):
                    continue
                # use path-based reach test if sprite provides it
                reached = False
                if hasattr(e, "reached_goal_on_path"):
                    reached = e.reached_goal_on_path(threshold=12)
                else:
                    dx = e.pos[0] - self.goal_pos[0]
                    dy = e.pos[1] - self.goal_pos[1]
                    reached = math.hypot(dx, dy) < 12

                if reached:
                    # enemy reached power source -> damage, then advance question
                    e.kill()
                    if self.snd_hit and self.sfx_enabled:
                        try:
                            self.snd_hit.play()
                        except:
                            pass
                    # now subtract life (only upon actual arrival)
                    if self.lives is not None:
                        self.lives -= 1
                    if self.lives is not None and self.lives <= 0:
                        self.state = "game_over"
                        try:
                            pygame.mixer.music.stop()
                        except:
                            pass
                    else:
                        # spawn the next question/enemy now that this one reached the goal
                        self.load_next_question()

            # handle question timer expiration (only when both timer and start are present)
            if (
                self.question_timer_ms is not None
                and self.question_timer_start is not None
                and self.state == "asking"
                and self.current_q
            ):
                elapsed = pygame.time.get_ticks() - self.question_timer_start
                remaining = max(0, int(self.question_timer_ms - elapsed))
                if remaining <= 0:
                    # treat as wrong answer: make enemies rush along path
                    for e in list(self.enemies):
                        if hasattr(e, "set_rush_to_goal"):
                            e.set_rush_to_goal(self.goal_pos)
                        else:
                            e.rush = True
                            e.goal_pos = self.goal_pos
                    if self.snd_rush and self.sfx_enabled:
                        try:
                            self.snd_rush.play()
                        except:
                            pass
                    # hide the overlay; DO NOT subtract life now; wait until arrival
                    self.state = "playing"

            # drawing
            screen.fill((24, 20, 28))

            # draw course (image preferred)
            course_img = self.graphics.get("course")
            if course_img:
                try:
                    scaled = pygame.transform.smoothscale(
                        course_img, (SCREEN_W, SCREEN_H)
                    )
                    screen.blit(scaled, (0, 0))
                except:
                    screen.fill((50, 40, 30))
            else:
                # fallback: soft background; draw ring once so devs can see path
                pygame.draw.rect(screen, (34, 28, 20), (0, 0, SCREEN_W, SCREEN_H))
                if self.path:
                    pts = [(int(x), int(y)) for (x, y) in self.path]
                    pygame.draw.lines(screen, (90, 70, 50), True, pts, 36)
                    pygame.draw.lines(screen, (120, 100, 80), True, pts, 24)
                    if self.spawn_pos:
                        pygame.draw.circle(
                            screen,
                            (60, 160, 60),
                            (int(self.spawn_pos[0]), int(self.spawn_pos[1])),
                            8,
                        )
                    if self.goal_pos:
                        pygame.draw.circle(
                            screen,
                            (200, 60, 60),
                            (int(self.goal_pos[0]), int(self.goal_pos[1])),
                            10,
                        )

            # draw towers/enemies/projectiles
            self.towers.draw(screen)
            self.enemies.draw(screen)
            self.projectiles.draw(screen)

            # HUD left: score / lives
            lives_display = "∞" if self.lives is None else str(self.lives)
            hud = font.render(
                f"Score: {self.score}   Lives: {lives_display}", True, (255, 255, 255)
            )
            screen.blit(hud, (10, 10))

            # HUD right: session / question timer / music info
            if self.session_time_ms is not None:
                remaining = max(0, int(self.session_time_ms - self.session_elapsed_ms))
                session_str = f"Session: {self.format_time_ms(remaining)}"
            else:
                session_str = "Session: ∞"

            if (
                self.question_timer_ms is not None
                and self.question_timer_start is not None
            ):
                elapsed = pygame.time.get_ticks() - self.question_timer_start
                qrem = max(0, int(self.question_timer_ms - elapsed))
                qstr = f"Q time: {self.format_time_ms(qrem)}"
            else:
                qstr = "Q time: ∞"

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

            sx = SCREEN_W - 10
            right1 = smallfont.render(session_str, True, (200, 200, 255))
            right2 = smallfont.render(qstr, True, (200, 200, 255))
            right3 = smallfont.render(music_label, True, (200, 200, 255))
            screen.blit(right1, (sx - right1.get_width(), 8))
            screen.blit(right2, (sx - right2.get_width(), 8 + right1.get_height() + 2))
            screen.blit(
                right3,
                (
                    sx - right3.get_width(),
                    8 + right1.get_height() + right2.get_height() + 6,
                ),
            )

            # question overlay
            if self.state == "asking" and self.current_q:
                overlay_rect, qlines, rects, meta = self.compute_overlay_layout(
                    bigfont, font
                )
                overlay = pygame.Surface(
                    (overlay_rect.w, overlay_rect.h), flags=pygame.SRCALPHA
                )
                overlay.fill((28, 28, 40, 220))
                screen.blit(overlay, (overlay_rect.x, overlay_rect.y))

                qy = overlay_rect.y + meta["TOP_PAD"]
                for line in qlines:
                    textsurf = bigfont.render(line, True, (255, 255, 255))
                    screen.blit(textsurf, (overlay_rect.x + meta["CHOICE_PAD_X"], qy))
                    qy += textsurf.get_height() + 4

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
                    # restart
                    if getattr(self.settings, "lives", None) is None:
                        self.lives = None
                    else:
                        self.lives = int(getattr(self.settings, "lives", 3))
                    self.score = 0
                    self.load_questions()
                    self.question_index = 0
                    self.load_next_question()
                    self.build_looped_path()
                    self.place_towers_along_path()
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


# Export for discover_games()
Game = TowerDefenseGame
