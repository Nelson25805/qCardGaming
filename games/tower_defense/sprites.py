# games/tower_defense/sprites.py
import pygame, math


class Creature(pygame.sprite.Sprite):
    def __init__(self, path_points, speed=60.0, hp=1, image=None, loop_segment=None):
        super().__init__()
        # image fallback
        if image is not None:
            try:
                self.image = image.convert_alpha()
            except:
                self.image = pygame.Surface((18, 18), pygame.SRCALPHA)
                pygame.draw.circle(self.image, (180, 80, 80), (9, 9), 9)
        else:
            self.image = pygame.Surface((18, 18), pygame.SRCALPHA)
            pygame.draw.circle(self.image, (180, 80, 80), (9, 9), 9)

        self.rect = self.image.get_rect(center=path_points[0])
        self.path = list(path_points)
        self.seg = 0
        self.pos = [float(self.rect.centerx), float(self.rect.centery)]
        self.speed = float(speed)  # px/sec
        self.hp = int(hp)
        self.loop_segment = loop_segment  # (start_idx, end_idx) or None
        self.reached_goal = False
        self.forced_direct_target = (
            None  # (x,y) target when sprinting directly to tower/goal
        )

    def update(self, dt):
        if self.reached_goal or self.hp <= 0:
            return

        if self.forced_direct_target is not None:
            tx, ty = self.forced_direct_target
            dx = tx - self.pos[0]
            dy = ty - self.pos[1]
            dist = math.hypot(dx, dy)
            if dist <= 1.0:
                # reached forced target -> treat as reached goal if target was goal
                self.pos[0] = tx
                self.pos[1] = ty
                self.rect.center = (int(self.pos[0]), int(self.pos[1]))
                # mark reached_goal only if target equals final path end
                if self.path:
                    last = self.path[-1]
                    if (int(last[0]), int(last[1])) == (int(tx), int(ty)):
                        self.reached_goal = True
                return
            travel = self.speed * (dt / 1000.0)
            if travel >= dist:
                self.pos[0] = tx
                self.pos[1] = ty
            else:
                self.pos[0] += (dx / dist) * travel
                self.pos[1] += (dy / dist) * travel
            self.rect.centerx = int(self.pos[0])
            self.rect.centery = int(self.pos[1])
            return

        # normal path-following behavior
        if self.seg >= len(self.path) - 1:
            self.reached_goal = True
            return

        target = self.path[self.seg + 1]
        dx = target[0] - self.pos[0]
        dy = target[1] - self.pos[1]
        dist = math.hypot(dx, dy)
        if dist <= 0.1:
            self.seg += 1
            if self.loop_segment and self.seg >= self.loop_segment[1]:
                self.seg = self.loop_segment[0]
            return

        travel = self.speed * (dt / 1000.0)
        if travel >= dist:
            self.pos[0] = target[0]
            self.pos[1] = target[1]
            self.seg += 1
            if self.loop_segment and self.seg >= self.loop_segment[1]:
                self.seg = self.loop_segment[0]
        else:
            self.pos[0] += (dx / dist) * travel
            self.pos[1] += (dy / dist) * travel

        self.rect.centerx = int(self.pos[0])
        self.rect.centery = int(self.pos[1])

    def take_damage(self, dmg=1):
        self.hp -= dmg
        if self.hp <= 0:
            self.kill()


class Projectile(pygame.sprite.Sprite):
    def __init__(self, x, y, vx, vy, dmg=1, image=None):
        super().__init__()
        if image is not None:
            try:
                self.image = image.convert_alpha()
            except:
                self.image = pygame.Surface((6, 6), pygame.SRCALPHA)
                pygame.draw.circle(self.image, (255, 220, 80), (3, 3), 3)
        else:
            self.image = pygame.Surface((6, 6), pygame.SRCALPHA)
            pygame.draw.circle(self.image, (255, 220, 80), (3, 3), 3)
        self.rect = self.image.get_rect(center=(x, y))
        self.vx = float(vx)
        self.vy = float(vy)
        self.dmg = int(dmg)

    def update(self, dt):
        self.rect.x += int(self.vx * (dt / 1000.0))
        self.rect.y += int(self.vy * (dt / 1000.0))
        # kill out of bounds
        if (
            self.rect.top > 1200
            or self.rect.bottom < -200
            or self.rect.left > 2000
            or self.rect.right < -200
        ):
            self.kill()


class Tower:
    def __init__(self, x, y, image=None, cooldown_ms=600):
        self.x = int(x)
        self.y = int(y)
        self.image = image
        self.cooldown_ms = int(cooldown_ms)
        self.cooldown_timer = 0  # ms remaining

    def update(self, dt):
        if self.cooldown_timer > 0:
            self.cooldown_timer = max(0, self.cooldown_timer - dt)

    def can_fire(self):
        return self.cooldown_timer <= 0

    def fire_at(self, target, projectile_image=None, proj_speed=480.0, dmg=1):
        """
        Returns a Projectile instance aimed at target sprite (assumes target has rect.center).
        Does NOT insert into any groups; caller should add it. Sets cooldown.
        """
        tx, ty = target.rect.centerx, target.rect.centery
        sx, sy = self.x, self.y
        dx = tx - sx
        dy = ty - sy
        dist = math.hypot(dx, dy)
        if dist <= 0.1:
            vx = 0.0
            vy = -proj_speed
        else:
            vx = (dx / dist) * proj_speed
            vy = (dy / dist) * proj_speed
        self.cooldown_timer = self.cooldown_ms
        return Projectile(sx, sy, vx, vy, dmg=dmg, image=projectile_image)
