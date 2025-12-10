# games/tower_defense/game.py
from pathlib import Path
import pygame, random, math
from .helpers import SCREEN_W, SCREEN_H
from . import sprites, resources
import quiz_loader, utils

MAX_CREATURES = 14
SPAWN_INTERVAL_MS = 1500


class TowerDefenseGame:
    def __init__(self, csv_path, screen=None, settings=None):
        self.csv_path = csv_path
        self.screen = screen
        self.settings = settings

        # quiz
        self.questions = []
        self.answer_pool = []

        # sfx
        self.sfx_bank = {}
        self.snd_shoot = None
        self.snd_impact = None
        self.snd_spawn = None
        self.snd_die = None
        self.snd_jam = None

        # graphics
        self.graphics = {
            "tower": None,
            "creature": None,
            "projectile": None,
            "background": None,
            "path": None,
        }

        # gameplay
        self.towers = []  # list of Tower objects
        self.creatures = None  # sprite.Group
        self.projectiles = None  # sprite.Group

        # state
        self.score = 0
        self.lives = 3
        self.state = "asking"
        self.current_q = None
        self.choices = []
        self.correct_choice_index = -1
        self.question_index = 0

        # timers
        self.finish_after_hit = False
        self.spawn_timer = 0
        self.muzzle_timer = 0

        # path
        self.path_points = []
        self.loop_segment = None

        # flags
        self.sfx_enabled = True
        self.music_enabled = False

        # session timer
        self.session_time_ms = None

    # -------------------------
    # questions & assets
    # -------------------------
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

    def load_sounds(self, folder=None):
        resources.load_sounds(self, folder)

    def load_graphics(self, folder=None):
        resources.load_graphics(self, folder)

    # -------------------------
    # path generation and towers
    # -------------------------
    def make_random_path(self):
        pts = []
        left_x = 60
        right_x = SCREEN_W - 60
        n_segments = random.randint(5, 8)
        xs = [
            int(left_x + i * (right_x - left_x) / (n_segments - 1))
            for i in range(n_segments)
        ]
        y_min = 100
        y_max = 80 + 240 - 24
        for x in xs:
            y = random.randint(y_min, y_max)
            pts.append((x, y))

        start = (left_x - 40, pts[0][1])
        end = (right_x + 40, pts[-1][1])
        pts.insert(0, start)
        pts.append(end)

        # create a small loop region
        if len(pts) >= 6:
            a = len(pts) // 2 - 1
            b = a + 2
            p_a = pts[a]
            p_b = pts[b]
            mx = (p_a[0] + p_b[0]) // 2
            my = (p_a[1] + p_b[1]) // 2
            offset = 24
            loop_points = [(mx, my - offset), (mx + offset, my), (mx, my + offset)]
            pts[a + 1 : a + 1] = loop_points
            self.loop_segment = (a + 1, a + 1 + len(loop_points))
        else:
            self.loop_segment = None

        self.path_points = pts

    def scatter_towers_along_path(self):
        """
        Place 3..6 towers along the path, offset to either side of the path for coverage.
        Picks indices along the path and offsets by perpendicular vector.
        """
        self.towers = []
        if not self.path_points:
            return
        n = max(3, min(6, len(self.path_points) // 2))
        indices = []
        step = max(1, len(self.path_points) // (n + 1))
        for i in range(1, len(self.path_points) - 1, step):
            indices.append(i)
            if len(indices) >= n:
                break
        # jitter indices a bit
        indices = [
            min(len(self.path_points) - 2, max(1, i + random.randint(-1, 1)))
            for i in indices
        ]

        for idx in indices:
            a = self.path_points[idx]
            b = self.path_points[min(idx + 1, len(self.path_points) - 1)]
            dx = b[0] - a[0]
            dy = b[1] - a[1]
            # perpendicular
            nx = -dy
            ny = dx
            nd = math.hypot(nx, ny)
            if nd == 0:
                nd = 1
            nx /= nd
            ny /= nd
            offset = random.randint(40, 90)
            side = random.choice([-1, 1])
            tx = a[0] + nx * offset * side
            ty = a[1] + ny * offset * side
            # clamp on-screen-ish
            tx = max(40, min(SCREEN_W - 40, int(tx)))
            ty = max(60, min(SCREEN_H - 60, int(ty)))
            tw_img = self.graphics.get("tower")
            tower = sprites.Tower(
                tx, ty, image=tw_img, cooldown_ms=random.randint(450, 900)
            )
            self.towers.append(tower)

    # -------------------------
    # creature spawning
    # -------------------------
    def _creature_speed_from_settings(self):
        tbq = None
        if getattr(self.settings, "time_between_questions", None) is not None:
            try:
                tbq = float(self.settings.time_between_questions)
            except:
                tbq = None
        if tbq is None:
            return 60.0, True
        tbq_clamped = max(1.0, min(600.0, tbq))
        speed = 160.0 * (3.0 / tbq_clamped)
        speed = max(20.0, min(200.0, speed))
        return speed, False

    def spawn_creature(self):
        speed, loop_mode = self._creature_speed_from_settings()
        img = self.graphics.get("creature")
        hp = 1
        loop_seg = self.loop_segment if loop_mode and self.loop_segment else None
        if not self.path_points:
            return
        c = sprites.Creature(
            self.path_points, speed=speed, hp=hp, image=img, loop_segment=loop_seg
        )
        self.creatures.add(c)
        if self.snd_spawn and self.sfx_enabled:
            try:
                self.snd_spawn.play()
            except:
                pass

    # -------------------------
    # setup & question logic
    # -------------------------
    def setup_objects(self):
        self.make_random_path()
        self.scatter_towers_along_path()
        self.creatures = pygame.sprite.Group()
        self.projectiles = pygame.sprite.Group()
        self.spawn_timer = 0

    def load_next_question(self):
        if not self.questions:
            self.current_q = None
            self.choices = []
            self.correct_choice_index = -1
            self.state = "asking"
            return

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

        self.current_q = self.questions[self.question_index]
        self.question_index += 1
        distractors = quiz_loader.make_distractors(
            self.current_q["a"], self.answer_pool
        )
        self.choices = distractors + [self.current_q["a"]]
        random.shuffle(self.choices)
        self.correct_choice_index = self.choices.index(self.current_q["a"])
        self.state = "asking"

    # -------------------------
    # run loop
    # -------------------------
    def run(self):
        pygame.init()
        try:
            pygame.mixer.init()
        except:
            pass
        screen = self.screen or pygame.display.set_mode((SCREEN_W, SCREEN_H))
        clock = pygame.time.Clock()
        font = pygame.font.Font(None, 18)
        bigfont = pygame.font.Font(None, 22)
        smallfont = pygame.font.Font(None, 16)

        # questions
        self.load_questions()
        self.load_next_question()

        # graphics & sounds
        try:
            self.load_graphics(Path("games") / "tower_defense" / "assets" / "Graphics")
        except:
            try:
                self.load_graphics()
            except:
                pass

        self.setup_objects()

        if self.settings is not None:
            if getattr(self.settings, "lives", None) is None:
                self.lives = None
            else:
                self.lives = int(self.settings.lives)
            self.sfx_enabled = bool(getattr(self.settings, "sfx", True))
            self.music_enabled = bool(getattr(self.settings, "music", False))

        # session timer
        if getattr(self.settings, "total_time", None) is None:
            self.session_time_ms = None
        else:
            try:
                self.session_time_ms = int(float(self.settings.total_time) * 1000)
            except:
                self.session_time_ms = None

        try:
            self.load_sounds(
                Path("games") / "tower_defense" / "assets" / "Sound Effects"
            )
        except:
            try:
                self.load_sounds()
            except:
                pass

        self.snd_shoot = self.sfx_bank.get("shoot") or self.sfx_bank.get("shot")
        self.snd_impact = self.sfx_bank.get("impact") or self.sfx_bank.get("hit")
        self.snd_spawn = self.sfx_bank.get("spawn")
        self.snd_die = self.sfx_bank.get("die") or self.sfx_bank.get("death")
        self.snd_jam = self.sfx_bank.get("jam")

        # music
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

        # overlay geometry
        OVERLAY_W = SCREEN_W - 200
        CHOICE_H = 40
        CHOICE_GAP = 8
        CHOICE_PAD_X = 16
        TOP_PAD = 12
        BOTTOM_PAD = 12
        MAX_OVERLAY_H = SCREEN_H - 120

        def compute_overlay_layout():
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
            overlay_y = SCREEN_H - overlay_h - 40
            overlay_rect = pygame.Rect(overlay_x, overlay_y, OVERLAY_W, overlay_h)
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

            # session timer tick
            if getattr(self, "session_time_ms", None) is not None:
                self.session_time_ms = max(0, self.session_time_ms - dt)
                if self.session_time_ms <= 0 and self.state not in ("won", "game_over"):
                    self.state = "game_over"
                    try:
                        pygame.mixer.music.stop()
                    except:
                        pass

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
                        overlay_rect, qlines, rects = compute_overlay_layout()
                        for i, r in enumerate(rects[: len(self.choices)]):
                            if r.collidepoint(mx, my):
                                if i == self.correct_choice_index:
                                    # correct: choose creature that is best-targeted by any tower
                                    if (
                                        len(self.creatures.sprites()) > 0
                                        and len(self.towers) > 0
                                    ):
                                        best_pair = None
                                        best_dist = 1e9
                                        # for each creature, find closest tower distance
                                        for c in self.creatures:
                                            # nearest tower to this creature
                                            t, d = None, 1e9
                                            for tw in self.towers:
                                                dd = math.hypot(
                                                    tw.x - c.rect.centerx,
                                                    tw.y - c.rect.centery,
                                                )
                                                if dd < d:
                                                    d = dd
                                                    t = tw
                                            if d < best_dist and t is not None:
                                                best_dist = d
                                                best_pair = (t, c)
                                        if best_pair is not None:
                                            tower, target_creature = best_pair
                                            if tower.can_fire():
                                                proj = tower.fire_at(
                                                    target_creature,
                                                    projectile_image=self.graphics.get(
                                                        "projectile"
                                                    ),
                                                )
                                                self.projectiles.add(proj)
                                                if self.snd_shoot and self.sfx_enabled:
                                                    try:
                                                        self.snd_shoot.play()
                                                    except:
                                                        pass
                                                self.muzzle_timer = 120
                                            # if last question & one_each, finish after hit
                                            last_q_and_one_each = getattr(
                                                self.settings, "question_mode", "loop"
                                            ) == "one_each" and self.question_index >= len(
                                                self.questions
                                            )
                                            if last_q_and_one_each:
                                                self.finish_after_hit = True
                                                self.state = "playing"
                                            else:
                                                self.load_next_question()
                                                if self.state in ("won", "game_over"):
                                                    try:
                                                        pygame.mixer.music.stop()
                                                    except:
                                                        pass
                                                else:
                                                    self.state = "playing"
                                        else:
                                            # fallback: award points and advance
                                            self.score += 100
                                            self.load_next_question()
                                    else:
                                        # no creatures/towers -> award points and advance
                                        self.score += 100
                                        self.load_next_question()
                                else:
                                    # incorrect -> cause nearest creature to sprint to power source immediately
                                    if len(self.creatures.sprites()) > 0:
                                        # pick creature nearest to end goal
                                        goal = (
                                            self.path_points[-1]
                                            if self.path_points
                                            else (SCREEN_W - 40, SCREEN_H - 40)
                                        )
                                        c = min(
                                            self.creatures.sprites(),
                                            key=lambda cc: math.hypot(
                                                cc.rect.centerx - goal[0],
                                                cc.rect.centery - goal[1],
                                            ),
                                        )
                                        # set forced direct target to goal and increase speed for sprint
                                        c.forced_direct_target = (
                                            int(goal[0]),
                                            int(goal[1]),
                                        )
                                        c.speed = max(180.0, c.speed * 2.5)
                                        # play jam/hurt sfx
                                        if self.snd_jam and self.sfx_enabled:
                                            try:
                                                self.snd_jam.play()
                                            except:
                                                pass
                                    # decrement lives (will also be handled when creature reaches goal)
                                    if self.lives is not None:
                                        # don't immediately subtract here — we wait until the creature reaches goal to deduct
                                        pass
                                    # advance question regardless (do not repeat)
                                    self.load_next_question()
                                break

            # spawn creatures as appropriate
            if self.state not in ("game_over", "won"):
                self.spawn_timer += dt
                interval = SPAWN_INTERVAL_MS
                tbq = (
                    getattr(self.settings, "time_between_questions", None)
                    if getattr(self, "settings", None)
                    else None
                )
                if tbq:
                    try:
                        tbqv = float(tbq)
                        interval = max(300, int(SPAWN_INTERVAL_MS * (tbqv / 10.0)))
                    except:
                        interval = SPAWN_INTERVAL_MS
                if self.spawn_timer >= interval and len(self.creatures) < MAX_CREATURES:
                    self.spawn_creature()
                    self.spawn_timer = 0

            # keyboard
            keys = pygame.key.get_pressed()
            if keys[pygame.K_q]:
                try:
                    pygame.mixer.music.stop()
                except:
                    pass
                return "quit"

            # update towers
            for tw in self.towers:
                tw.update(dt)

            # update creatures
            for c in list(self.creatures):
                c.update(dt)
                if c.reached_goal:
                    # creature reached goal -> deduct life and kill creature
                    try:
                        c.kill()
                    except:
                        pass
                    if self.lives is not None:
                        self.lives -= 1
                        if self.lives <= 0:
                            self.state = "game_over"
                            try:
                                pygame.mixer.music.stop()
                            except:
                                pass

            # update projectiles
            self.projectiles.update(dt)

            # projectile vs creature collisions
            for p in list(self.projectiles):
                hits = pygame.sprite.spritecollide(p, self.creatures, dokill=False)
                if hits:
                    for h in hits:
                        h.take_damage(p.dmg)
                        self.score += 50
                    if self.snd_impact and self.sfx_enabled:
                        try:
                            self.snd_impact.play()
                        except:
                            pass
                    p.kill()

            # if finish_after_hit: wait for projectiles to clear, then advance/win
            if self.finish_after_hit:
                if len(self.projectiles) == 0:
                    self.load_next_question()
                    if self.state in ("won", "game_over"):
                        try:
                            pygame.mixer.music.stop()
                        except:
                            pass
                    self.finish_after_hit = False
                    if self.state not in ("won", "game_over"):
                        self.state = "asking"

            # drawing
            screen.fill((18, 18, 28))

            bg = self.graphics.get("background")
            if bg:
                try:
                    bgs = pygame.transform.smoothscale(bg, (SCREEN_W, SCREEN_H))
                    screen.blit(bgs, (0, 0))
                except:
                    pass

            # draw path
            path_img = self.graphics.get("path")
            wall_rect = pygame.Rect(60, 80, SCREEN_W - 120, 240)
            if path_img:
                try:
                    path_s = pygame.transform.smoothscale(
                        path_img, (wall_rect.w, wall_rect.h)
                    )
                    screen.blit(path_s, (wall_rect.x, wall_rect.y))
                except:
                    pass
            else:
                if len(self.path_points) >= 2:
                    pygame.draw.lines(
                        screen, (120, 120, 100), False, self.path_points, 8
                    )
                    pygame.draw.lines(
                        screen, (150, 150, 130), False, self.path_points, 2
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

            # draw towers
            for tw in self.towers:
                if tw.image:
                    r = tw.image.get_rect(center=(tw.x, tw.y))
                    screen.blit(tw.image, r)
                else:
                    pygame.draw.rect(
                        screen, (80, 110, 90), (tw.x - 10, tw.y - 16, 20, 32)
                    )
                    pygame.draw.circle(screen, (200, 200, 80), (tw.x, tw.y - 22), 5)

            # draw creatures & projectiles
            self.creatures.draw(screen)
            self.projectiles.draw(screen)

            # muzzle flash
            if getattr(self, "muzzle_timer", 0) > 0:
                self.muzzle_timer = max(0, self.muzzle_timer - dt)
                # flash at each tower that fired recently (simple: flash at tower positions that are cooling down)
                for tw in self.towers:
                    if tw.cooldown_timer > 0 and tw.cooldown_timer < 500:
                        pygame.draw.circle(screen, (255, 220, 80), (tw.x, tw.y - 22), 6)

            # HUD left
            lives_display = "∞" if self.lives is None else str(self.lives)
            hud = font.render(
                f"Score: {self.score}   Lives: {lives_display}", True, (255, 255, 255)
            )
            screen.blit(hud, (10, 10))

            # right-side HUD
            def format_time_ms(ms):
                if ms is None:
                    return "∞"
                s = max(0, int(ms // 1000))
                h = s // 3600
                m = (s % 3600) // 60
                sec = s % 60
                if h > 0:
                    return f"{h}:{m:02d}:{sec:02d}"
                return f"{m}:{sec:02d}"

            session_str = (
                f"Session: {format_time_ms(self.session_time_ms)}"
                if getattr(self, "session_time_ms", None) is not None
                else "Session: ∞"
            )
            tbq = (
                getattr(self.settings, "time_between_questions", None)
                if getattr(self, "settings", None)
                else None
            )
            qstr = f"Q time: {int(tbq)}s" if tbq is not None else "Q time: ∞"
            music_label = "Music: Off"
            if getattr(self, "music_enabled", False):
                mc = (
                    getattr(self.settings, "music_choice", "")
                    if getattr(self, "settings", None)
                    else ""
                )
                music_label = (
                    f"Music: On ({Path(mc).name})" if mc else "Music: On (none)"
                )
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
                overlay_rect, qlines, rects = compute_overlay_layout()
                overlay = pygame.Surface(
                    (overlay_rect.w, overlay_rect.h), flags=pygame.SRCALPHA
                )
                overlay.fill((28, 28, 40, 200))
                screen.blit(overlay, (overlay_rect.x, overlay_rect.y))
                qy = overlay_rect.y + TOP_PAD
                for line in qlines:
                    textsurf = bigfont.render(line, True, (255, 255, 255))
                    screen.blit(textsurf, (overlay_rect.x + CHOICE_PAD_X, qy))
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
                    self.setup_objects()
                    if getattr(self.settings, "total_time", None) is None:
                        self.session_time_ms = None
                    else:
                        try:
                            self.session_time_ms = int(
                                float(self.settings.total_time) * 1000
                            )
                        except:
                            self.session_time_ms = None
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
