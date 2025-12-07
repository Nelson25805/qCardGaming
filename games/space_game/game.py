import pygame, random, math, sys
from pathlib import Path
import quiz_loader
import utils
from .helpers import SCREEN_W, SCREEN_H, BULLET_SPEED_MAG, format_time_ms
from . import sprites, resources


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
        # Use None for unlimited lives, integer for finite lives
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
        self.sfx_bank = {}

        # graphics storage (surfaces) - populated by resources.load_graphics()
        self.graphics = {"invaders": [], "player": None, "bullet": None}

        # timers
        self.question_timer_ms = None
        self.session_time_ms = None
        self.session_elapsed_ms = 0
        # flags set from settings
        self.sfx_enabled = True
        self.music_enabled = False
        self.muzzle_flash = True

        # enemy / wave config
        self.enemies_per_wave = 18
        # continuous descent speed (pixels per ms). computed after player exists.
        self.enemy_descent_speed_px_per_ms = 0.0
        # store initial Y layout top for wrapping purposes
        self.enemy_initial_top = 50

        # When True, the current correct-answer will finish the run only after the
        # targeted enemy is destroyed (so we can play the firing/hit animation).
        self.finish_after_hit = False

        # --- Compatibility wrapper methods (paste inside SpaceGame class) ---

    def load_sounds(self, folder=None):
        try:
            resources.load_sounds(self, folder)
        except Exception:
            # preserve old behavior of failing silently on sound issues
            pass

    def load_graphics(self, folder=None):
        try:
            resources.load_graphics(self, folder)
        except Exception:
            pass

    def start_music(self):
        try:
            return resources.start_music(self)
        except Exception:
            return False

    def stop_music(self):
        try:
            resources.stop_music(self)
        except Exception:
            pass

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
        # Sprites; pass loaded graphics if available
        self.player = sprites.Player(
            SCREEN_W // 2, SCREEN_H - 40, image=self.graphics.get("player")
        )
        self.player_group = pygame.sprite.Group(self.player)
        self.bullets = pygame.sprite.Group()
        self.enemies = pygame.sprite.Group()
        # spawn initial wave based on mode & question count
        self.spawn_enemies_for_mode_initial()

    def spawn_enemies(self, count=None):
        """Spawn `count` enemies into rows/cols (cols=6). Each enemy gets attribute init_y to enable wrapping."""
        if count is None:
            count = self.enemies_per_wave
        self.enemies.empty()
        cols = 6
        # compute rows needed
        rows = (count + cols - 1) // cols
        total_w = cols * 40 + (cols - 1) * 10
        start_x = (SCREEN_W - total_w) // 2
        start_y = self.enemy_initial_top
        placed = 0
        inv_images = self.graphics.get("invaders", []) or []
        for r in range(rows):
            for c in range(cols):
                if placed >= count:
                    break
                x = start_x + c * (40 + 10)
                y = start_y + r * (30 + 10)
                img = None
                if inv_images:
                    img = random.choice(inv_images)
                e = sprites.Enemy(x, y, image=img)
                e.init_y = y
                self.enemies.add(e)
                placed += 1

    def spawn_enemies_for_mode_initial(self):
        """Choose initial spawn count based on settings."""
        if getattr(self.settings, "question_mode", "loop") == "one_each":
            total_questions = len(self.questions)
            # question_index counts how many times load_next_question was already invoked.
            # compute remaining by subtracting (question_index - 1) if load_next_question called before.
            remaining = max(0, total_questions - max(0, self.question_index - 1))
            spawn_count = min(self.enemies_per_wave, max(0, remaining))
            if spawn_count > 0:
                self.spawn_enemies(spawn_count)
            else:
                self.enemies.empty()
        else:
            self.spawn_enemies(self.enemies_per_wave)

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

        # if we're at/after the end and question_mode is one_each, finish the run
        if self.question_index >= len(self.questions):
            if getattr(self.settings, "question_mode", "loop") == "one_each":
                # finished the set -> determine win/lose based on remaining lives
                self.current_q = None
                self.choices = []
                self.correct_choice_index = -1
                self.question_timer_ms = None
                # If lives is None (unlimited) or still >0 then this is a win
                if (self.lives is None) or (
                    isinstance(self.lives, int) and self.lives > 0
                ):
                    self.state = "won"
                else:
                    self.state = "game_over"
                return
            else:
                # loop mode -> reshuffle & reset index
                self.question_index = 0
                random.shuffle(self.questions)

        # normal case: load the question at question_index
        self.current_q = self.questions[self.question_index]
        # increment question index to indicate we've prepared this question (used for remaining calculations)
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

    # -- helper to clean up when run finishes --
    def _cleanup_after_finish(self):
        """Stop audio/timers/bullets when the run finishes (won or game_over)."""
        # stop music
        resources.stop_music(self)
        # clear bullets so no stray bullets keep states changing
        try:
            if self.bullets:
                for b in list(self.bullets):
                    b.kill()
        except Exception:
            pass
        self.pending_target = None
        # stop question timer
        self.question_timer_ms = None
        # reset finish flag
        self.finish_after_hit = False

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

        # load questions
        self.load_questions()

        # prepare the first question BEFORE spawning so spawn logic can base on question counts
        self.load_next_question()

        # load graphics now (after pygame.init()) so sprites can use them
        try:
            resources.load_graphics(self, Path("assets") / "Graphics")
        except Exception:
            try:
                resources.load_graphics(self, "assets")
            except:
                pass

        # setup sprites & enemies (spawn initial wave respecting mode)
        self.setup_pygame_objects()

        # apply settings defaults: lives, music, sfx, enemy speed multiplier, timers
        if self.settings is not None:
            if getattr(self.settings, "lives", None) is None:
                # represent unlimited lives with None
                self.lives = None
            else:
                self.lives = int(self.settings.lives)
            self.initial_lives = self.lives
            # enemy speed multiplier (horizontal speed)
            self.enemy_speed = self.enemy_speed * float(
                getattr(self.settings, "enemy_speed_multiplier", 1.0)
            )
            # total session timer (seconds) -> convert to milliseconds counter
            total_time = getattr(self.settings, "total_time", None)
            if total_time is None:
                self.session_time_ms = None
            else:
                # settings.total_time stored in seconds; convert to ms
                self.session_time_ms = int(total_time * 1000)
            # time between questions (stored in settings as seconds)
            tbq = getattr(self.settings, "time_between_questions", None)
            if tbq is None:
                self.time_between_questions_ms = None
            else:
                try:
                    tbq_val = float(tbq)
                except Exception:
                    try:
                        tbq_val = float(
                            "".join([c for c in str(tbq) if (c.isdigit() or c == ".")])
                        )
                    except Exception:
                        tbq_val = None
                if tbq_val is None:
                    self.time_between_questions_ms = None
                else:
                    if tbq_val > 1000:
                        self.time_between_questions_ms = int(tbq_val)
                    else:
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

        # load sounds (try assets folder)
        try:
            resources.load_sounds(self, Path("assets") / "Sound Effects")
        except Exception:
            try:
                resources.load_sounds(self, "assets")
            except:
                pass

        # compute enemy vertical descent speed:
        # If session_time_ms is finite, calculate a per-ms speed so enemies reach player's top at session end.
        # Use the topmost enemy init Y as a baseline.
        if (
            self.session_time_ms is not None
            and self.session_time_ms > 0
            and self.player is not None
        ):
            # determine top of enemies (use configured enemy_initial_top)
            top_y = self.enemy_initial_top
            player_target_y = max(0, self.player.rect.top)
            descent_needed = max(0, player_target_y - top_y - 8)  # small margin
            # pixels per ms
            self.enemy_descent_speed_px_per_ms = descent_needed / float(
                self.session_time_ms
            )
        else:
            # unlimited -> no gradual downward progress (we will wrap instead)
            self.enemy_descent_speed_px_per_ms = 0.0

        # start music if enabled
        if self.music_enabled:
            resources.start_music(self)

        # timers
        self.session_elapsed_ms = 0

        running = True
        while running:
            dt = clock.tick(60)  # dt in ms

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    # stop music and quit
                    resources.stop_music(self)
                    running = False
                    return "quit"
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    # only allow clicks when in asking state and there's an active question
                    if self.state == "asking" and self.current_q:
                        mx, my = event.pos
                        rects = utils.choice_rects(SCREEN_W, SCREEN_H)
                        for i, r in enumerate(rects[: len(self.choices)]):
                            if r.collidepoint(mx, my):
                                if i == self.correct_choice_index:
                                    # correct answer
                                    if len(self.enemies.sprites()) > 0:
                                        # create bullet that targets an enemy
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
                                        b = sprites.Bullet(
                                            start_x,
                                            start_y,
                                            vx=vx,
                                            vy=vy,
                                            image=self.graphics.get("bullet"),
                                        )
                                        b.target = target
                                        self.bullets.add(b)
                                        self.pending_target = target
                                        self.muzzle_timer = 160

                                        # If this is the last question in one_each mode, we want to play the
                                        # animation first and then show the win screen. Detect that case:
                                        last_q_and_one_each = getattr(
                                            self.settings, "question_mode", "loop"
                                        ) == "one_each" and self.question_index >= len(
                                            self.questions
                                        )

                                        if last_q_and_one_each:
                                            # mark that we should finish after the hit occurs
                                            self.finish_after_hit = True
                                            # DO NOT call load_next_question() now — wait for hit
                                            # keep state as "playing" to allow bullet animation
                                            self.state = "playing"
                                            if self.fire_snd and self.sfx_enabled:
                                                try:
                                                    self.fire_snd.play()
                                                except:
                                                    pass
                                        else:
                                            # normal behavior: advance question now (so UI updates immediately)
                                            self.load_next_question()
                                            # If loading next question finished the run, cleanup; otherwise go to playing
                                            if self.state in ("won", "game_over"):
                                                self._cleanup_after_finish()
                                            else:
                                                self.state = "playing"
                                                if self.fire_snd and self.sfx_enabled:
                                                    try:
                                                        self.fire_snd.play()
                                                    except:
                                                        pass
                                    else:
                                        # no enemies (edge-case) -> give points and advance question
                                        self.score += 100
                                        self.load_next_question()
                                        if self.state not in ("won", "game_over"):
                                            self.state = "asking"
                                        else:
                                            self._cleanup_after_finish()
                                else:
                                    # incorrect -> decrement only when lives are finite (not None)
                                    if self.lives is not None:
                                        self.lives -= 1
                                    # check for game over only if lives are numeric
                                    if self.lives is not None and self.lives <= 0:
                                        self.state = "game_over"
                                        self._cleanup_after_finish()
                                    else:
                                        self.load_next_question()
                                break

            keys = pygame.key.get_pressed()

            # update session timer (only when not in game_over or won)
            if getattr(
                self, "session_time_ms", None
            ) is not None and self.state not in ("game_over", "won"):
                self.session_elapsed_ms += dt
                if self.session_elapsed_ms >= self.session_time_ms:
                    # session time up -> game over
                    self.state = "game_over"
                    self._cleanup_after_finish()

            # update question timer (only when asking)
            if (
                self.state == "asking"
                and getattr(self, "question_timer_ms", None) is not None
            ):
                self.question_timer_ms -= dt
                if self.question_timer_ms <= 0:
                    # time up for this question -> lose a life (unless lives unlimited)
                    if self.lives is not None:
                        self.lives -= 1
                    # advance question or end
                    if self.lives is not None and self.lives <= 0:
                        self.state = "game_over"
                        self._cleanup_after_finish()
                    else:
                        qmode = (
                            getattr(self.settings, "question_mode", "loop")
                            if getattr(self, "settings", None)
                            else "loop"
                        )
                        if qmode == "one_each" and self.question_index >= len(
                            self.questions
                        ):
                            # finished the set due to hitting time on the last question
                            # decide win/lose based on remaining lives
                            if (self.lives is None) or (
                                isinstance(self.lives, int) and self.lives > 0
                            ):
                                self.state = "won"
                            else:
                                self.state = "game_over"
                            self._cleanup_after_finish()
                        else:
                            self.load_next_question()

            # ---------- game updates ----------
            if self.state == "playing":
                self.player.update(keys)
                self.bullets.update()
                self.enemies.update()

                # apply horizontal movement
                if self.pending_target is None:
                    move_x = self.enemy_dir * self.enemy_speed * dt
                    for e in self.enemies:
                        e.rect.x += move_x

                # bounce horizontally and small drop on bounce (kept)
                if self.enemies and self.pending_target is None:
                    leftmost = min(e.rect.left for e in self.enemies)
                    rightmost = max(e.rect.right for e in self.enemies)
                    if leftmost <= 0 or rightmost >= SCREEN_W:
                        self.enemy_dir *= -1
                        for e in self.enemies:
                            e.rect.y += 10

                # apply continuous descent if computed
                if abs(self.enemy_descent_speed_px_per_ms) > 0.0:
                    for e in self.enemies:
                        e.rect.y += self.enemy_descent_speed_px_per_ms * dt

                # check wrap/arrival logic
                reached_player = False
                for e in self.enemies:
                    if e.rect.bottom >= self.player.rect.top:
                        reached_player = True
                        break

                if reached_player:
                    # finite session -> game over (they reached player)
                    if self.session_time_ms is not None:
                        self.state = "game_over"
                        self._cleanup_after_finish()
                    else:
                        # unlimited -> wrap back to initial y positions
                        for e in self.enemies:
                            if hasattr(e, "init_y"):
                                e.rect.y = e.init_y

                # collisions
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

                    # If we were waiting to finish after this hit (final-question correct),
                    # then advance the question/run now (this causes state = 'won' typically).
                    if self.finish_after_hit:
                        # loading next question will detect end and set state to 'won'
                        self.load_next_question()
                        # cleanup/stop music if finished
                        if self.state in ("won", "game_over"):
                            self._cleanup_after_finish()
                        self.finish_after_hit = False
                        # do NOT spawn more waves if finished; otherwise spawn as usual below

                    # when all enemies in current wave are cleared:
                    if len(self.enemies) == 0:
                        # FIRST prepare next question (this may set state to "won" or "game_over")
                        # Note: if finish_after_hit was True above, question advancement already happened.
                        if not self.finish_after_hit:
                            self.load_next_question()

                        # If the run finished (win/lose) don't spawn a new wave
                        if self.state in ("game_over", "won"):
                            # cleanup and stop music
                            self._cleanup_after_finish()
                            # don't spawn new wave
                        else:
                            # then spawn next wave if appropriate
                            if (
                                getattr(self.settings, "question_mode", "loop")
                                == "one_each"
                            ):
                                total_questions = len(self.questions)
                                # remaining questions = total - (question_index - 1)
                                remaining = max(
                                    0, total_questions - max(0, self.question_index - 1)
                                )
                                if remaining > 0:
                                    self.spawn_enemies(
                                        min(self.enemies_per_wave, remaining)
                                    )
                            else:
                                # loop mode: always spawn standard wave
                                self.spawn_enemies(self.enemies_per_wave)

                        # after handling wave spawn/load question, continue
                        if len(self.enemies) == 0:
                            # If load_next_question ended the game (one_each done), don't change state
                            if self.state not in ("game_over", "won"):
                                self.state = "asking"

                # forced hit via proximity (targeted bullet)
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

                                # If we were waiting to finish after this hit (final-question correct),
                                # then advance the question/run now (this causes state = 'won' typically).
                                if self.finish_after_hit:
                                    self.load_next_question()
                                    if self.state in ("won", "game_over"):
                                        self._cleanup_after_finish()
                                    self.finish_after_hit = False

                                # spawn next wave if appropriate (unless finished)
                                if self.state not in ("game_over", "won"):
                                    if (
                                        getattr(self.settings, "question_mode", "loop")
                                        == "one_each"
                                    ):
                                        total_questions = len(self.questions)
                                        remaining = max(
                                            0,
                                            total_questions
                                            - max(0, self.question_index - 1),
                                        )
                                        if remaining > 0:
                                            self.spawn_enemies(
                                                min(self.enemies_per_wave, remaining)
                                            )
                                    else:
                                        self.spawn_enemies(self.enemies_per_wave)
                                # go back to asking if not game over/won
                                if self.state not in ("game_over", "won"):
                                    self.state = "asking"
                                break

                if len(self.bullets) == 0 and self.state not in ("game_over", "won"):
                    self.state = "asking"

            elif self.state == "asking":
                self.player.update(keys)
                self.bullets.update()
                # small horizontal movement while asking
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
                # continuous descent while asking as well
                if abs(self.enemy_descent_speed_px_per_ms) > 0.0:
                    for e in self.enemies:
                        e.rect.y += self.enemy_descent_speed_px_per_ms * dt
                # wrap or detect arrival as in playing
                reached_player = any(
                    e.rect.bottom >= self.player.rect.top for e in self.enemies
                )
                if reached_player:
                    if self.session_time_ms is not None:
                        self.state = "game_over"
                        self._cleanup_after_finish()
                    else:
                        for e in self.enemies:
                            if hasattr(e, "init_y"):
                                e.rect.y = e.init_y

            # ---------- drawing ----------
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
            lives_display = "∞" if self.lives is None else str(self.lives)
            hud = font.render(
                f"Score: {self.score}   Lives: {lives_display}", True, (255, 255, 255)
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
                # show different headline for win vs loss
                if self.state == "won":
                    headline = bigfont.render("YOU WIN!", True, (80, 220, 120))
                else:
                    headline = bigfont.render("GAME OVER", True, (255, 50, 50))

                screen.blit(
                    headline,
                    (SCREEN_W // 2 - headline.get_width() // 2, SCREEN_H // 2 - 40),
                )

                # optional details: show score / progress (you can customize)
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

                # Restart / quit handling
                keys = pygame.key.get_pressed()
                if keys[pygame.K_r]:
                    # restart using settings defaults
                    if getattr(self.settings, "lives", None) is None:
                        self.lives = None
                    else:
                        self.lives = int(getattr(self.settings, "lives", 3))
                    self.initial_lives = self.lives
                    self.score = 0

                    # reload questions and reset indices
                    self.load_questions()
                    self.question_index = 0
                    self.load_next_question()

                    # respawn enemies appropriate for mode
                    self.setup_pygame_objects()

                    # reset timers
                    self.session_elapsed_ms = 0

                    # go back to asking
                    self.state = "asking"

                    # restart music if enabled in settings
                    if self.music_enabled:
                        resources.start_music(self)

                if keys[pygame.K_q]:
                    # quit from win/lose: ensure music stopped then exit
                    resources.stop_music(self)
                    running = False
                    return "quit"

            pygame.display.flip()

        # ensure music stopped when leaving run
        resources.stop_music(self)
        pygame.quit()
