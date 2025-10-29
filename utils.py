"""
utils.py
Small UI and helper utilities used by the main menu and games.
"""

import pygame


def wrap_text(text, font, max_width):
    words = text.split(" ")
    lines = []
    cur = ""
    for w in words:
        if font.size((cur + " " + w).strip())[0] <= max_width:
            cur = (cur + " " + w).strip()
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def choice_rects(screen_w, screen_h):
    w = 340
    h = 42
    gap = 12
    x = (screen_w - w) // 2
    y0 = screen_h // 2
    rects = []
    for i in range(4):
        rects.append(pygame.Rect(x, y0 + i * (h + gap), w, h))
    return rects


def button_rect(mid_x, mid_y, w=300, h=50):
    r = pygame.Rect(0, 0, w, h)
    r.center = (mid_x, mid_y)
    return r
