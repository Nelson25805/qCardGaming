"""Sprite classes: Player, Bullet, Enemy for the Space Game."""
import pygame
from .helpers import SCREEN_W, SCREEN_H, BULLET_SPEED_MAG

class Player(pygame.sprite.Sprite):
    def __init__(self, x, y, image=None):
        super().__init__()
        if image is not None:
            try:
                surf = image
                max_w = 72
                if surf.get_width() > max_w:
                    h = int(surf.get_height() * (max_w / surf.get_width()))
                    surf = pygame.transform.smoothscale(surf, (max_w, h))
                self.image = surf.convert_alpha()
            except Exception:
                self.image = pygame.Surface((50, 20), pygame.SRCALPHA)
                pygame.draw.rect(self.image, (50, 200, 50), (0, 0, 50, 20), border_radius=4)
        else:
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
    def __init__(self, x, y, vx=0.0, vy=0.0, image=None):
        super().__init__()
        if image is not None:
            try:
                surf = image
                if surf.get_width() > 16:
                    surf = pygame.transform.smoothscale(surf, (10, 18))
                self.image = surf.convert_alpha()
            except Exception:
                self.image = pygame.Surface((6, 12), pygame.SRCALPHA)
                pygame.draw.rect(self.image, (255, 255, 0), (0, 0, 6, 12))
        else:
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
    def __init__(self, x, y, image=None):
        super().__init__()
        if image is not None:
            try:
                surf = image
                max_w = 40
                if surf.get_width() != max_w:
                    h = int(surf.get_height() * (max_w / surf.get_width()))
                    surf = pygame.transform.smoothscale(surf, (max_w, h))
                self.image = surf.convert_alpha()
            except Exception:
                self.image = pygame.Surface((40, 30))
                self.image.fill((200, 50, 50))
        else:
            self.image = pygame.Surface((40, 30))
            self.image.fill((200, 50, 50))
        self.rect = self.image.get_rect(topleft=(x, y))
        self.init_y = y
