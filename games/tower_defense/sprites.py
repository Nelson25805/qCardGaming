import pygame
import math


class Enemy(pygame.sprite.Sprite):
    """
    Enemy that follows a provided path (list of (x,y)).
    If `rush` is False it will loop around the path indefinitely.
    If `rush` is True and a goal_index is set it will advance along the path
    forward (wrapping) until it reaches the goal index.
    """

    def __init__(self, path, speed=60.0, image=None):
        super().__init__()
        self.path = list(path)[:]  # list of (x,y)
        self.speed = float(speed)  # pixels / second
        self.path_index = (
            0  # index of current waypoint (we're between path_index and path_index+1)
        )
        self.rush = False
        self.goal_index = (
            None  # index in path corresponding to goal when rushing along path
        )
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

        # start at path[0] if available, else (0,0)
        start = (0, 0)
        if self.path:
            start = self.path[0]
        self.pos = [float(start[0]), float(start[1])]
        self.rect = self.image.get_rect(center=(int(self.pos[0]), int(self.pos[1])))

    def update(self, dt):
        """
        dt: seconds since last update
        """
        if self.dead:
            return

        if not self.path:
            # nothing to follow
            return

        # Decide next waypoint index (always forward along path)
        next_idx = (self.path_index + 1) % len(self.path)
        target_x, target_y = self.path[next_idx]

        # If we are in rush mode but goal_index is defined we should keep moving forward
        # along the path until we reach goal_index (arrive near that waypoint).
        cur_target_idx = next_idx
        target_is_goal = False
        if self.rush and (self.goal_index is not None):
            # We still always step toward path[next_idx] and increment path_index when arrived,
            # and we'll consider arrival "reached goal" when path_index == goal_index and close enough.
            # (This preserves consistent forward motion along the circular path.)
            # Compute the target waypoint the same as normal (next_idx).
            cur_target_idx = next_idx
            target_is_goal = cur_target_idx == self.goal_index

        # Move toward target waypoint
        tx, ty = target_x, target_y
        dx = tx - self.pos[0]
        dy = ty - self.pos[1]
        dist = math.hypot(dx, dy)
        if dist <= 1e-6:
            # we've essentially reached next waypoint — advance path_index
            self.path_index = cur_target_idx
        else:
            speed = self.speed
            # optionally increase speed slightly while rushing to make it feel urgent
            if self.rush:
                speed = self.speed * 1.8
            step = speed * dt
            if step >= dist:
                # arrive at target
                self.pos[0] = tx
                self.pos[1] = ty
                self.path_index = cur_target_idx
            else:
                self.pos[0] += (dx / dist) * step
                self.pos[1] += (dy / dist) * step

        # update rect
        self.rect.centerx = int(self.pos[0])
        self.rect.centery = int(self.pos[1])

    def set_rush_to_goal(self, goal_pos):
        """
        Put this enemy into "rush along path" mode so it will advance forward
        along the path until it reaches whichever path waypoint is closest to goal_pos.
        goal_pos should be a (x,y) tuple.
        """
        self.rush = True
        # find nearest path waypoint to provided goal_pos
        if not self.path:
            self.goal_index = None
            return
        gx, gy = float(goal_pos[0]), float(goal_pos[1])
        best = 0
        bestd = None
        for i, (px, py) in enumerate(self.path):
            d = (px - gx) ** 2 + (py - gy) ** 2
            if bestd is None or d < bestd:
                bestd = d
                best = i
        self.goal_index = best

    def reached_goal_on_path(self, threshold=12):
        """
        Returns True only if this enemy is rushing and its current path_index
        corresponds to the goal_index and its distance to that waypoint is within threshold.
        """
        if not self.rush or self.goal_index is None:
            return False
        gx, gy = self.path[self.goal_index]
        dx = self.pos[0] - gx
        dy = self.pos[1] - gy
        return (dx * dx + dy * dy) <= (threshold * threshold)

    def stop_rush(self):
        self.rush = False
        self.goal_index = None


class Tower(pygame.sprite.Sprite):
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
        p = Projectile(self.pos, target_pos, speed=speed, image=image)
        projectile_group.add(p)
        return p


class Projectile(pygame.sprite.Sprite):
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
        dx = self.target[0] - self.pos[0]
        dy = self.target[1] - self.pos[1]
        dist = math.hypot(dx, dy) or 1.0
        self.vx = (dx / dist) * self.speed
        self.vy = (dy / dist) * self.speed

    def update(self, dt):
        step_x = self.vx * dt
        step_y = self.vy * dt
        dx = self.target[0] - self.pos[0]
        dy = self.target[1] - self.pos[1]
        dist = math.hypot(dx, dy)
        if math.hypot(step_x, step_y) >= dist:
            self.kill()
            return
        self.pos[0] += step_x
        self.pos[1] += step_y
        self.rect.centerx = int(self.pos[0])
        self.rect.centery = int(self.pos[1])
