from pathlib import Path
import pygame, random, math
from .helpers import SCREEN_W, SCREEN_H
from . import sprites, resources
import quiz_loader, utils

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
        self.graphics = {'player': None, 'bullet': None, 'bottle_frames': []}
        self.player = None
        self.player_group = None
        self.bullets = None
        self.bottles = None
        self.score = 0
        self.lives = 3
        self.state = 'asking'
        self.current_q = None
        self.choices = []
        self.correct_choice_index = -1
        self.question_index = 0

    def load_questions(self):
        self.questions = quiz_loader.load_questions(self.csv_path)
        self.answer_pool = [q['a'] for q in self.questions]
        if getattr(self.settings, 'question_order', 'random') == 'bottom':
            self.questions.reverse()
        elif getattr(self.settings, 'question_order', 'random') == 'random':
            random.shuffle(self.questions)

    def load_sounds(self, folder=None):
        resources.load_sounds(self, folder)

    def load_graphics(self, folder=None):
        resources.load_graphics(self, folder)

    def setup_objects(self):
        self.player = sprites.Player(SCREEN_W//2, SCREEN_H - 24, image=self.graphics.get('player'))
        self.player_group = pygame.sprite.Group(self.player)
        self.bullets = pygame.sprite.Group()
        self.bottles = pygame.sprite.Group()
        frames = self.graphics.get('bottle_frames', [])
        cols = 8
        rows = 3
        start_x = SCREEN_W//2 - (cols*28)//2 + 14
        start_y = 120
        for r in range(rows):
            for c in range(cols):
                x = start_x + c*28
                y = start_y + r*48
                b = sprites.Bottle(x, y, frames)
                self.bottles.add(b)

    def load_next_question(self):
        if not self.questions:
            self.current_q = None
            self.choices = []
            self.correct_choice_index = -1
            self.state = 'asking'
            return
        if self.question_index >= len(self.questions):
            if getattr(self.settings, 'question_mode', 'loop') == 'one_each':
                # finish
                self.current_q = None
                self.choices = []
                self.correct_choice_index = -1
                if (self.lives is None) or (isinstance(self.lives, int) and self.lives > 0):
                    self.state = 'won'
                else:
                    self.state = 'game_over'
                return
            self.question_index = 0
            random.shuffle(self.questions)
        self.current_q = self.questions[self.question_index]
        self.question_index += 1
        distractors = quiz_loader.make_distractors(self.current_q['a'], self.answer_pool)
        self.choices = distractors + [self.current_q['a']]
        random.shuffle(self.choices)
        self.correct_choice_index = self.choices.index(self.current_q['a'])
        self.state = 'asking'

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

        self.load_questions()
        self.load_next_question()

        # load graphics & sounds from package assets first
        try:
            self.load_graphics(Path('games') / 'cowboy_shooter' / 'assets' / 'Graphics')
        except:
            self.load_graphics()
        self.setup_objects()

        if self.settings is not None:
            if getattr(self.settings, 'lives', None) is None:
                self.lives = None
            else:
                self.lives = int(self.settings.lives)
            self.sfx_enabled = bool(getattr(self.settings, 'sfx', True))
            self.music_enabled = bool(getattr(self.settings, 'music', False))

        try:
            self.load_sounds(Path('games') / 'cowboy_shooter' / 'assets' / 'Sound Effects')
        except:
            self.load_sounds()

        self.snd_shot = self.sfx_bank.get('shot')
        self.snd_break = self.sfx_bank.get('break')
        self.snd_jam = self.sfx_bank.get('jam')

        if self.music_enabled:
            mc = getattr(self.settings, 'music_choice', '') or ''
            mus_candidates = [
                Path('games') / 'cowboy_shooter' / 'assets' / 'Music' / mc,
                Path('assets') / 'music' / mc,
                Path(mc)
            ]
            for p in mus_candidates:
                if p.exists() and p.is_file():
                    try:
                        pygame.mixer.music.load(str(p))
                        pygame.mixer.music.play(-1)
                        break
                    except:
                        pass

        running = True
        while running:
            dt = clock.tick(60)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    try: pygame.mixer.music.stop()
                    except: pass
                    running = False
                    return 'quit'
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.state == 'asking' and self.current_q:
                        mx, my = event.pos
                        rects = utils.choice_rects(SCREEN_W, SCREEN_H)
                        for i, r in enumerate(rects[:len(self.choices)]):
                            if r.collidepoint(mx, my):
                                if i == self.correct_choice_index:
                                    if len(self.bottles.sprites())>0:
                                        target = min(self.bottles.sprites(), key=lambda b: abs(b.rect.centerx - self.player.aim_x))
                                        start_x = self.player.rect.centerx
                                        start_y = self.player.rect.top - 10
                                        dx = target.rect.centerx - start_x
                                        dy = target.rect.centery - start_y
                                        dist = math.hypot(dx, dy)
                                        if dist <= 0.1:
                                            vx = 0.0; vy = -10.0
                                        else:
                                            vx = (dx/dist)*10.0
                                            vy = (dy/dist)*10.0
                                        bl = sprites.Bullet(start_x, start_y, vx=vx, vy=vy, image=self.graphics.get('bullet'))
                                        self.bullets.add(bl)
                                        if self.snd_shot and self.sfx_enabled:
                                            try: self.snd_shot.play()
                                            except: pass
                                        self.state = 'playing'
                                    else:
                                        self.score += 100
                                        self.load_next_question()
                                else:
                                    if self.snd_jam and self.sfx_enabled:
                                        try: self.snd_jam.play()
                                        except: pass
                                    if self.lives is not None:
                                        self.lives -= 1
                                    if self.lives is not None and self.lives <= 0:
                                        self.state = 'game_over'
                                        try: pygame.mixer.music.stop()
                                        except: pass
                                    else:
                                        self.load_next_question()
                                break

            keys = pygame.key.get_pressed()
            self.player.update(keys)
            self.bullets.update()
            for b in list(self.bullets):
                hits = pygame.sprite.spritecollide(b, self.bottles, dokill=False)
                if hits:
                    for hit in hits:
                        hit.start_break()
                        b.kill()
                        if self.snd_break and self.sfx_enabled:
                            try: self.snd_break.play()
                            except: pass
                        self.score += 100
                    self.state = 'asking'

            for bottle in list(self.bottles):
                bottle.update(dt)

            screen.fill((60,50,30))
            wall_rect = pygame.Rect(60,80,SCREEN_W-120,240)
            pygame.draw.rect(screen, (90,70,50), wall_rect)
            self.bottles.draw(screen)
            self.player_group.draw(screen)
            self.bullets.draw(screen)

            lives_display = '∞' if self.lives is None else str(self.lives)
            hud = font.render(f"Score: {self.score}   Lives: {lives_display}", True, (255,255,255))
            screen.blit(hud, (10,10))

            if self.state == 'asking' and self.current_q:
                overlay = pygame.Surface((SCREEN_W-60, SCREEN_H-220))
                overlay.set_alpha(220)
                overlay.fill((30,30,40))
                ox = 30; oy = 80
                screen.blit(overlay, (ox, oy))
                qlines = utils.wrap_text(self.current_q['q'], bigfont, SCREEN_W-120)
                qy = oy + 12
                for line in qlines:
                    textsurf = bigfont.render(line, True, (255,255,255))
                    screen.blit(textsurf, (ox+18, qy))
                    qy += textsurf.get_height()+4
                rects = utils.choice_rects(SCREEN_W, SCREEN_H)
                for i, r in enumerate(rects[:len(self.choices)]):
                    pygame.draw.rect(screen, (80,80,120), r, border_radius=6)
                    lines = utils.wrap_text(self.choices[i], font, r.w-16)
                    ty = r.y + 6
                    for ln in lines:
                        screen.blit(font.render(ln, True, (255,255,255)), (r.x+8, ty))
                        ty += font.get_height()+2

            elif self.state in ('game_over','won'):
                if self.state == 'won':
                    headline = bigfont.render('YOU WIN!', True, (80,220,120))
                else:
                    headline = bigfont.render('GAME OVER', True, (255,50,50))
                screen.blit(headline, (SCREEN_W//2-headline.get_width()//2, SCREEN_H//2-40))
                details = font.render(f"Score: {self.score}", True, (200,200,200))
                screen.blit(details, (SCREEN_W//2-details.get_width()//2, SCREEN_H//2))
                hint = font.render('Press R to restart or Q to quit.', True, (255,255,255))
                screen.blit(hint, (SCREEN_W//2-hint.get_width()//2, SCREEN_H//2+30))
                keys = pygame.key.get_pressed()
                if keys[pygame.K_r]:
                    if getattr(self.settings, 'lives', None) is None:
                        self.lives = None
                    else:
                        self.lives = int(getattr(self.settings, 'lives', 3))
                    self.score = 0
                    self.load_questions()
                    self.question_index = 0
                    self.load_next_question()
                    self.setup_objects()
                    self.state = 'asking'
                    if self.music_enabled:
                        try: pygame.mixer.music.play(-1)
                        except: pass
                if keys[pygame.K_q]:
                    try: pygame.mixer.music.stop()
                    except: pass
                    running = False
                    return 'quit'

            pygame.display.flip()

        try: pygame.mixer.music.stop()
        except: pass
        pygame.quit()
