import pygame
from .helpers import SCREEN_W, SCREEN_H

class Player(pygame.sprite.Sprite):
    def __init__(self, x, y, image=None):
        super().__init__()
        if image is not None:
            try:
                self.image = image.convert_alpha()
            except:
                self.image = pygame.Surface((48,68), pygame.SRCALPHA)
                pygame.draw.rect(self.image, (120,80,40), (0,0,48,68), border_radius=6)
        else:
            self.image = pygame.Surface((48,68), pygame.SRCALPHA)
            pygame.draw.rect(self.image, (120,80,40), (0,0,48,68), border_radius=6)
        self.rect = self.image.get_rect(midbottom=(x,y))
        self.aim_x = x

    def update(self, keys):
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.aim_x -= 6
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.aim_x += 6
        self.aim_x = max(40, min(self.aim_x, SCREEN_W-40))

class Bullet(pygame.sprite.Sprite):
    def __init__(self, x, y, vx=0, vy=-10.0, image=None):
        super().__init__()
        if image is not None:
            try:
                self.image = image.convert_alpha()
            except:
                self.image = pygame.Surface((6,12), pygame.SRCALPHA)
                pygame.draw.rect(self.image, (200,200,80), (0,0,6,12))
        else:
            self.image = pygame.Surface((6,12), pygame.SRCALPHA)
            pygame.draw.rect(self.image, (200,200,80), (0,0,6,12))
        self.rect = self.image.get_rect(center=(x,y))
        self.posx = float(self.rect.centerx)
        self.posy = float(self.rect.centery)
        self.vx = float(vx)
        self.vy = float(vy)

    def update(self):
        self.posx += self.vx
        self.posy += self.vy
        self.rect.centerx = int(self.posx)
        self.rect.centery = int(self.posy)
        if self.rect.bottom < -50 or self.rect.top > SCREEN_H + 50 or self.rect.left > SCREEN_W + 50 or self.rect.right < -50:
            self.kill()

class Bottle(pygame.sprite.Sprite):
    def __init__(self, x, y, frames=None):
        super().__init__()
        self.frames = frames or []
        if self.frames:
            self.image = self.frames[0]
        else:
            self.image = pygame.Surface((18,28), pygame.SRCALPHA)
            pygame.draw.rect(self.image, (100,180,120), (0,0,18,28))
        self.rect = self.image.get_rect(center=(x,y))
        self.anim_idx = 0
        self.anim_timer = 0
        self.anim_delay = 80
        self.breaking = False

    def start_break(self):
        if not self.breaking:
            self.breaking = True
            self.anim_idx = 0
            self.anim_timer = 0

    def update(self, dt=0):
        if self.breaking and self.frames:
            self.anim_timer += dt
            if self.anim_timer >= self.anim_delay:
                self.anim_timer = 0
                self.anim_idx += 1
                if self.anim_idx < len(self.frames):
                    self.image = self.frames[self.anim_idx]
                else:
                    self.kill()
