# games/tower_defense/sprites.py
import math
import pygame
from .helpers import SCREEN_W, SCREEN_H


class Enemy(pygame.sprite.Sprite):
    def __init__(self, path_points, speed=60.0, image=None):
        """
        path_points: list[(x,y)] forming the loop path (the enemy will follow indices 0..n-1 and wrap)
        speed: pixels/sec along path
        """
        super().__init__()
        self.path = path_points
        self.speed = float(speed)
        self.pos = list(self.path[0])  # start at first point
        self.index = 0
        self.t = 0.0  # interpolation between index and index+1 (0..1)
        self.rush = False  # when True: rush straight to goal (provided as attribute goal_pos set externally)
        self.goal_pos = None
        self.image = image if image is not None else self._make_placeholder()
        self.rect = self.image.get_rect(center=self.pos)
        self.dead = False

    def _make_placeholder(self):
        surf = pygame.Surface((24, 24), pygame.SRCALPHA)
        pygame.draw.circle(surf, (200, 60, 60), (12, 12), 12)
        pygame.draw.circle(surf, (255, 180, 180), (9, 9), 3)
        return surf

    def update(self, dt):
        if self.dead:
            return
        if self.rush and self.goal_pos is not None:
            # straight-line rush to goal (linear movement)
            dx = self.goal_pos[0] - self.pos[0]
            dy = self.goal_pos[1] - self.pos[1]
            dist = math.hypot(dx, dy)
            if dist <= 1.0:
                self.pos[0], self.pos[1] = self.goal_pos
            else:
                vx = (dx / dist) * self.speed * dt
                vy = (dy / dist) * self.speed * dt
                self.pos[0] += vx
                self.pos[1] += vy
        else:
            # follow looped path by stepping along segments proportional to dt*speed
            remaining = self.speed * dt
            while remaining > 0 and not self.dead:
                p0 = self.path[self.index]
                p1 = self.path[(self.index + 1) % len(self.path)]
                seg_dx = p1[0] - p0[0]
                seg_dy = p1[1] - p0[1]
                seg_len = math.hypot(seg_dx, seg_dy)
                # position along segment in absolute pixels
                abs_pos = self.index_pos(seg_len)
                # distance left on current segment
                to_end = (1.0 - self.t) * seg_len if seg_len > 0 else 0
                step = min(remaining, to_end)
                if seg_len > 0:
                    frac = step / seg_len
                else:
                    frac = 0
                self.t += frac
                if self.t >= 1.0 - 1e-6:
                    # move to next segment
                    self.index = (self.index + 1) % len(self.path)
                    self.t = 0.0
                # update pos
                p0 = self.path[self.index]
                p1 = self.path[(self.index + 1) % len(self.path)]
                self.pos[0] = p0[0] + (p1[0] - p0[0]) * self.t
                self.pos[1] = p0[1] + (p1[1] - p0[1]) * self.t
                remaining -= step
        self.rect.center = (int(self.pos[0]), int(self.pos[1]))

    def index_pos(self, seg_len):
        """helper, returns current absolute distance along current segment"""
        return self.index * seg_len + self.t * seg_len


class Tower(pygame.sprite.Sprite):
    def __init__(self, x, y, image=None):
        super().__init__()
        if image is not None:
            self.image = image
        else:
            self.image = pygame.Surface((28, 28), pygame.SRCALPHA)
            pygame.draw.rect(self.image, (80, 140, 60), (0, 0, 28, 28), border_radius=6)
        self.rect = self.image.get_rect(center=(x, y))
        self.pos = (x, y)

    def shoot_at(self, target_pos, projectile_group, image=None, speed=400.0):
        # spawn a projectile targeted at target_pos
        proj = Projectile(
            self.rect.centerx, self.rect.centery, target_pos, image=image, speed=speed
        )
        projectile_group.add(proj)
        return proj


class Projectile(pygame.sprite.Sprite):
    def __init__(self, x, y, target_pos, image=None, speed=400.0):
        super().__init__()
        if image is not None:
            self.image = image
        else:
            self.image = pygame.Surface((6, 6), pygame.SRCALPHA)
            pygame.draw.circle(self.image, (255, 220, 80), (3, 3), 3)
        self.rect = self.image.get_rect(center=(x, y))
        self.pos = [float(x), float(y)]
        self.target = tuple(target_pos)
        self.speed = float(speed)
        dx = self.target[0] - self.pos[0]
        dy = self.target[1] - self.pos[1]
        dist = math.hypot(dx, dy)
        if dist > 0:
            self.vx = dx / dist * self.speed
            self.vy = dy / dist * self.speed
        else:
            self.vx = 0
            self.vy = -self.speed
        self.dead = False

    def update(self, dt=0):
        if self.dead:
            return
        self.pos[0] += self.vx * dt
        self.pos[1] += self.vy * dt
        self.rect.center = (int(self.pos[0]), int(self.pos[1]))
        # very large bounds kill
        if (
            self.pos[0] < -100
            or self.pos[1] < -100
            or self.pos[0] > SCREEN_W + 100
            or self.pos[1] > SCREEN_H + 100
        ):
            self.kill()
