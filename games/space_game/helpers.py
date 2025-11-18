"""Helper constants and small utilities for the Space Game package."""
import math

SCREEN_W = 800
SCREEN_H = 600
BULLET_SPEED_MAG = 12.0

def format_time_ms(ms):
    """Format milliseconds as M:SS. If ms is None, return the infinity symbol."""
    if ms is None:
        return "∞"
    if ms < 0:
        ms = 0
    s = int(ms // 1000)
    m = s // 60
    s = s % 60
    return f"{m}:{s:02d}"
