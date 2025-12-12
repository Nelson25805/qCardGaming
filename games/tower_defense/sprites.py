import pygame, math
class Enemy(pygame.sprite.Sprite):
    def __init__(self, path, speed=60.0, image=None):
        super().__init__()
        self.path = path or [(0,0)]
        self.image = image.convert_alpha() if (image is not None and hasattr(image,'convert_alpha')) else None
        if self.image is None:
            surf = pygame.Surface((24,24), pygame.SRCALPHA)
            pygame.draw.circle(surf, (200,60,60), (12,12), 12)
            self.image = surf
        self.rect = self.image.get_rect()
        self.idx = 0
        self.pos = [float(self.path[0][0]), float(self.path[0][1])]
        self.rect.center = (int(self.pos[0]), int(self.pos[1]))
        self.speed = float(speed)
        self.rush = False
        self.goal_index = None
        self.dead = False
    def set_goal_index(self, idx):
        self.goal_index = int(idx)
        self.rush = True
    def update(self, dt):
        if self.dead:
            return
        if not self.rush:
            L = len(self.path)
            if L < 2:
                return
            next_idx = (self.idx + 1) % L
            nx, ny = self.path[next_idx]
            dx = nx - self.pos[0]
            dy = ny - self.pos[1]
            dist = math.hypot(dx, dy)
            if dist <= 1.0:
                self.pos[0] = nx; self.pos[1] = ny; self.idx = next_idx
            else:
                step = self.speed * dt
                self.pos[0] += dx / dist * step; self.pos[1] += dy / dist * step
        else:
            if self.goal_index is None:
                target = self.path[0]
                tx,ty = target
                dx = tx - self.pos[0]; dy = ty - self.pos[1]
                dist = math.hypot(dx,dy) or 1.0
                step = self.speed * 2.2 * dt
                if step >= dist:
                    self.pos[0] = tx; self.pos[1] = ty
                else:
                    self.pos[0] += dx / dist * step; self.pos[1] += dy / dist * step
            else:
                L = len(self.path)
                if L < 2: return
                next_idx = (self.idx + 1) % L
                nx, ny = self.path[next_idx]
                dx = nx - self.pos[0]; dy = ny - self.pos[1]
                dist = math.hypot(dx,dy) or 1.0
                step = self.speed * 2.5 * dt
                if step >= dist:
                    self.pos[0] = nx; self.pos[1] = ny; self.idx = next_idx
                else:
                    self.pos[0] += dx / dist * step; self.pos[1] += dy / dist * step
                if self.idx == self.goal_index:
                    self.rush = False
        self.rect.center = (int(self.pos[0]), int(self.pos[1]))
class Projectile(pygame.sprite.Sprite):
    def __init__(self, start_pos, target_pos, speed=320.0, image=None):
        super().__init__()
        self.image = image.convert_alpha() if (image is not None and hasattr(image,'convert_alpha')) else None
        if self.image is None:
            surf = pygame.Surface((8,8), pygame.SRCALPHA)
            pygame.draw.circle(surf, (240,220,120), (4,4), 4)
            self.image = surf
        self.rect = self.image.get_rect(center=(int(start_pos[0]), int(start_pos[1])))
        self.pos = [float(start_pos[0]), float(start_pos[1])]
        self.target = (float(target_pos[0]), float(target_pos[1]))
        self.speed = float(speed)
    def update(self, dt):
        tx,ty = self.target
        dx = tx - self.pos[0]; dy = ty - self.pos[1]
        dist = math.hypot(dx,dy)
        if dist <= 2.0:
            self.kill(); return
        step = self.speed * dt
        if step >= dist:
            self.pos[0] = tx; self.pos[1] = ty
        else:
            self.pos[0] += dx / dist * step; self.pos[1] += dy / dist * step
        self.rect.center = (int(self.pos[0]), int(self.pos[1]))
class Tower(pygame.sprite.Sprite):
    def __init__(self, x, y, image=None):
        super().__init__()
        self.image = image.convert_alpha() if (image is not None and hasattr(image,'convert_alpha')) else None
        if self.image is None:
            surf = pygame.Surface((28,28), pygame.SRCALPHA)
            pygame.draw.rect(surf, (80,120,200), (0,0,28,28), border_radius=6)
            pygame.draw.circle(surf, (180,200,240), (14,14), 6)
            self.image = surf
        self.rect = self.image.get_rect(center=(int(x), int(y)))
        self.pos = (float(x), float(y))
    def shoot_at(self, target_pos, projectile_group, image=None):
        from .sprites import Projectile
        proj = Projectile(self.pos, target_pos, speed=360.0, image=image)
        projectile_group.add(proj)
        return proj
