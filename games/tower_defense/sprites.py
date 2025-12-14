import pygame
import math


class Enemy(pygame.sprite.Sprite):
    """
    Enemy that follows a provided path (list of (x,y)).
    If `rush` is False it will loop around the path indefinitely.
    If `rush` is True it will run straight toward .goal_pos and be
    considered to have 'reached' the goal when close enough.
    """

    def __init__(self, path, speed=60.0, image=None):
        super().__init__()
        self.path = list(path)[:]  # list of (x,y)
        self.speed = float(speed)  # pixels / second
        self.path_index = 0
        self.rush = False
        self.looping = True
        self.goal_pos = None
        self.dead = False

        if image is not None:
            try:
                self.image = image.convert_alpha()
            except Exception:
                self.image = pygame.Surface((20, 20), pygame.SRCALPHA)
                pygame.draw.circle(self.image, (200, 60, 60), (10, 10), 10)
        else:
            self.image = pygame.Surface((20, 20), pygame.SRCALPHA)
            pygame.draw.circle(self.image, (200, 60, 60), (10, 10), 10)

        # start at path[0] if available
        start = (0, 0)
        if self.path:
            start = self.path[0]
        self.pos = [float(start[0]), float(start[1])]
        self.rect = self.image.get_rect(center=(int(self.pos[0]), int(self.pos[1])))

    def update(self, dt):
        if self.dead:
            return

        # If rushing, head directly to goal_pos
        if self.rush and self.goal_pos is not None:
            gx, gy = self.goal_pos
            dx = gx - self.pos[0]
            dy = gy - self.pos[1]
            dist = math.hypot(dx, dy)
            if dist <= 1e-6:
                # already at goal
                self.pos[0] = gx
                self.pos[1] = gy
            else:
                # move towards goal
                vx = (dx / dist) * self.speed * dt
                vy = (dy / dist) * self.speed * dt
                # if would overshoot, clamp to goal
                if math.hypot(vx, vy) >= dist:
                    self.pos[0] = gx
                    self.pos[1] = gy
                else:
                    self.pos[0] += vx
                    self.pos[1] += vy
        else:
            # Normal looping behavior: follow path points, wrap-around
            if not self.path:
                return
            # target is next path point
            next_idx = (self.path_index + 1) % len(self.path)
            tx, ty = self.path[next_idx]
            dx = tx - self.pos[0]
            dy = ty - self.pos[1]
            dist = math.hypot(dx, dy)
            if dist <= 1e-6:
                # Immediately advance
                self.path_index = next_idx
            else:
                # move toward target
                step = self.speed * dt
                if step >= dist:
                    # arrive at target
                    self.pos[0] = tx
                    self.pos[1] = ty
                    self.path_index = next_idx
                else:
                    self.pos[0] += (dx / dist) * step
                    self.pos[1] += (dy / dist) * step

        # update rect for collisions/drawing
        self.rect.centerx = int(self.pos[0])
        self.rect.centery = int(self.pos[1])

    def set_rush_to_goal(self, goal_pos):
        """Call this to force the enemy to run directly to the provided goal."""
        self.rush = True
        self.goal_pos = (float(goal_pos[0]), float(goal_pos[1]))


class Tower(pygame.sprite.Sprite):
    """
    Simple tower sprite located at (x,y). shoot_at() creates a Projectile that travels
    toward the given target_pos and is added to the provided group.
    """

    def __init__(self, x, y, image=None):
        super().__init__()
        self.pos = (float(x), float(y))
        if image is not None:
            try:
                self.image = image.convert_alpha()
            except Exception:
                self.image = pygame.Surface((28, 28), pygame.SRCALPHA)
                pygame.draw.rect(
                    self.image, (100, 140, 200), (0, 0, 28, 28), border_radius=6
                )
        else:
            self.image = pygame.Surface((28, 28), pygame.SRCALPHA)
            pygame.draw.rect(
                self.image, (100, 140, 200), (0, 0, 28, 28), border_radius=6
            )
        self.rect = self.image.get_rect(center=(int(self.pos[0]), int(self.pos[1])))

    def shoot_at(self, target_pos, projectile_group, image=None, speed=400.0):
        """Create a projectile heading toward `target_pos`, add to projectile_group and return it."""
        p = Projectile(self.pos, target_pos, speed=speed, image=image)
        projectile_group.add(p)
        return p


class Projectile(pygame.sprite.Sprite):
    """
    Projectile that moves toward a fixed target position. Kills itself on arrival.
    """

    def __init__(self, start_pos, target_pos, speed=400.0, image=None):
        super().__init__()
        self.start = (float(start_pos[0]), float(start_pos[1]))
        self.target = (float(target_pos[0]), float(target_pos[1]))
        self.speed = float(speed)
        if image is not None:
            try:
                self.image = image.convert_alpha()
            except Exception:
                self.image = pygame.Surface((8, 8), pygame.SRCALPHA)
                pygame.draw.circle(self.image, (220, 220, 100), (4, 4), 4)
        else:
            self.image = pygame.Surface((8, 8), pygame.SRCALPHA)
            pygame.draw.circle(self.image, (220, 220, 100), (4, 4), 4)
        self.rect = self.image.get_rect(center=(int(self.start[0]), int(self.start[1])))
        self.pos = [float(self.start[0]), float(self.start[1])]
        # direction
        dx = self.target[0] - self.pos[0]
        dy = self.target[1] - self.pos[1]
        dist = math.hypot(dx, dy) or 1.0
        self.vx = (dx / dist) * self.speed
        self.vy = (dy / dist) * self.speed

    def update(self, dt):
        step_x = self.vx * dt
        step_y = self.vy * dt
        # distance to target
        dx = self.target[0] - self.pos[0]
        dy = self.target[1] - self.pos[1]
        dist = math.hypot(dx, dy)
        if math.hypot(step_x, step_y) >= dist:
            # arrive
            self.kill()
            return
        self.pos[0] += step_x
        self.pos[1] += step_y
        self.rect.centerx = int(self.pos[0])
        self.rect.centery = int(self.pos[1])
