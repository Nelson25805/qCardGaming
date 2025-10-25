"""
games/space_game.py
Contains SpaceGame class encapsulating the trajectory v3 logic as a reusable module.
"""

import pygame, random, math, sys
from pathlib import Path
import quiz_loader
import utils

SCREEN_W, SCREEN_H = 800, 600
BULLET_SPEED_MAG = 12.0

class SpaceGame:
    def __init__(self, csv_path, screen=None):
        self.csv_path = csv_path
        self.screen = screen  # optional external pygame surface
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
        self.pending_target = None
        self.muzzle_timer = 0
        self.state = 'asking'
        self.current_q = None
        self.choices = []
        self.correct_choice_index = 0
        self.question_index = 0
        # pygame resources
        self.fire_snd = None
        self.hit_snd = None

    # -- loading / setup --
    def load_questions(self):
        self.questions = quiz_loader.load_questions(self.csv_path)
        self.answer_pool = [q['a'] for q in self.questions]
        random.shuffle(self.questions)

    def setup_pygame_objects(self):
        # Sprites
        self.player = Player(SCREEN_W//2, SCREEN_H-40)
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
                self.enemies.add(Enemy(x,y))

    # -- quiz helper --
    def load_next_question(self):
        if not self.questions:
            return
        if self.question_index >= len(self.questions):
            self.question_index = 0
            random.shuffle(self.questions)
        self.current_q = self.questions[self.question_index]
        self.question_index += 1
        distractors = quiz_loader.make_distractors(self.current_q['a'], self.answer_pool)
        self.choices = distractors + [self.current_q['a']]
        random.shuffle(self.choices)
        self.correct_choice_index = self.choices.index(self.current_q['a'])
        self.state = 'asking'

    # -- sounds --
    def load_sounds(self, folder):
        base = Path(folder)
        try:
            self.fire_snd = pygame.mixer.Sound(str(base / 'fire.wav'))
        except:
            self.fire_snd = None
        try:
            self.hit_snd = pygame.mixer.Sound(str(base / 'hit.wav'))
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

        # load questions and setup sprites
        self.load_questions()
        self.setup_pygame_objects()
        self.load_next_question()

        running = True
        while running:
            dt = clock.tick(60)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    return 'quit'
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.state == 'asking':
                        mx,my = event.pos
                        rects = utils.choice_rects(SCREEN_W, SCREEN_H)
                        for i,r in enumerate(rects):
                            if r.collidepoint(mx,my):
                                if i == self.correct_choice_index:
                                    if len(self.enemies.sprites()) > 0:
                                        target = min(self.enemies.sprites(), key=lambda e: abs(e.rect.centerx - self.player.rect.centerx))
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
                                        self.state = 'playing'
                                        if self.fire_snd:
                                            try: self.fire_snd.play()
                                            except: pass
                                    else:
                                        self.score += 100
                                        if not self.enemies: self.spawn_enemies()
                                        self.load_next_question()
                                        self.state = 'asking'
                                else:
                                    self.lives -= 1
                                    if self.lives <= 0:
                                        self.state = 'game_over'
                                    else:
                                        self.load_next_question()
                                break

            keys = pygame.key.get_pressed()
            if self.state == 'playing':
                self.player.update(keys)
                self.bullets.update()
                self.enemies.update()

                if self.pending_target is None:
                    move_x = self.enemy_dir * self.enemy_speed * dt
                    for e in self.enemies: e.rect.x += move_x

                if self.enemies and self.pending_target is None:
                    leftmost = min(e.rect.left for e in self.enemies)
                    rightmost = max(e.rect.right for e in self.enemies)
                    if leftmost <= 0 or rightmost >= SCREEN_W:
                        self.enemy_dir *= -1
                        for e in self.enemies: e.rect.y += 10

                hits = pygame.sprite.groupcollide(self.enemies, self.bullets, True, True)
                if hits:
                    self.score += 100 * len(hits)
                    if self.hit_snd:
                        try: self.hit_snd.play()
                        except: pass
                    if self.pending_target is not None:
                        self.pending_target = None
                    if not self.enemies:
                        self.spawn_enemies()
                    self.load_next_question()

                # forced hit via proximity
                if self.pending_target is not None:
                    for b in list(self.bullets):
                        if getattr(b, 'target', None) is self.pending_target:
                            dx = b.posx - self.pending_target.rect.centerx
                            dy = b.posy - self.pending_target.rect.centery
                            dist = math.hypot(dx, dy)
                            collision_radius = max(14, (self.pending_target.rect.width + self.pending_target.rect.height) // 6)
                            if dist <= collision_radius:
                                try:
                                    self.pending_target.kill()
                                except:
                                    pass
                                b.kill()
                                self.score += 100
                                if self.hit_snd:
                                    try: self.hit_snd.play()
                                    except: pass
                                self.pending_target = None
                                if not self.enemies:
                                    self.spawn_enemies()
                                self.load_next_question()
                                break

                if len(self.bullets) == 0:
                    self.state = 'asking'

            elif self.state == 'asking':
                self.player.update(keys)
                self.bullets.update()
                self.enemies.update()
                move_x = self.enemy_dir * self.enemy_speed * dt * 0.2
                for e in self.enemies: e.rect.x += move_x
                if self.enemies:
                    leftmost = min(e.rect.left for e in self.enemies)
                    rightmost = max(e.rect.right for e in self.enemies)
                    if leftmost <= 0 or rightmost >= SCREEN_W:
                        self.enemy_dir *= -1
                        for e in self.enemies: e.rect.y += 5

            # draw
            screen.fill((20,20,40))
            self.enemies.draw(screen)
            self.bullets.draw(screen)
            self.player_group.draw(screen)

            if self.muzzle_timer > 0:
                self.muzzle_timer -= dt
                mx = self.player.rect.centerx; my = self.player.rect.top - 6
                pygame.draw.circle(screen, (255,220,80), (mx,my), 8)

            hud = font.render(f"Score: {self.score}   Lives: {self.lives}", True, (255,255,255))
            screen.blit(hud, (10,10))

            if self.state == 'asking' and self.current_q:
                overlay = pygame.Surface((SCREEN_W - 60, SCREEN_H - 220))
                overlay.set_alpha(220)
                overlay.fill((30,30,60))
                ox = 30; oy = 80
                screen.blit(overlay, (ox,oy))
                qlines = utils.wrap_text(self.current_q['q'], bigfont, SCREEN_W-120)
                qy = oy + 12
                for line in qlines:
                    textsurf = bigfont.render(line, True, (255,255,255))
                    screen.blit(textsurf, (ox+18, qy))
                    qy += textsurf.get_height() + 4
                rects = utils.choice_rects(SCREEN_W, SCREEN_H)
                for i, r in enumerate(rects):
                    pygame.draw.rect(screen, (80,80,120), r, border_radius=6)
                    lines = utils.wrap_text(self.choices[i], font, r.w-16)
                    ty = r.y + 6
                    for ln in lines:
                        screen.blit(font.render(ln, True, (255,255,255)), (r.x+8, ty))
                        ty += font.get_height() + 2

            elif self.state == 'game_over':
                go = bigfont.render("GAME OVER", True, (255,50,50))
                screen.blit(go, (SCREEN_W//2 - go.get_width()//2, SCREEN_H//2 - 40))
                hint = font.render("Press R to restart or Q to quit.", True, (255,255,255))
                screen.blit(hint, (SCREEN_W//2 - hint.get_width()//2, SCREEN_H//2 + 10))
                keys = pygame.key.get_pressed()
                if keys[pygame.K_r]:
                    self.lives = 3; self.score = 0; self.spawn_enemies(); self.load_next_question(); self.state = 'asking'
                if keys[pygame.K_q]:
                    running = False
                    return 'quit'

            pygame.display.flip()

        pygame.quit()

# --- Sprite classes used by the SpaceGame ---
class Player(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.image = pygame.Surface((50, 20), pygame.SRCALPHA)
        pygame.draw.rect(self.image, (50,200,50), (0,0,50,20), border_radius=4)
        self.rect = self.image.get_rect(center=(x,y))
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
        self.image = pygame.Surface((6,12), pygame.SRCALPHA)
        pygame.draw.rect(self.image, (255,255,0), (0,0,6,12))
        self.rect = self.image.get_rect(center=(x,y))
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
        if (self.rect.bottom < -50 or self.rect.top > SCREEN_H+50 or self.rect.left > SCREEN_W+50 or self.rect.right < -50):
            self.kill()

class Enemy(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.image = pygame.Surface((40,30))
        self.image.fill((200,50,50))
        self.rect = self.image.get_rect(topleft=(x,y))
