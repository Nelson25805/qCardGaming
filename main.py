"""
main.py - modular launcher with main menu and settings screen
"""

import pygame, sys, os
from pathlib import Path
from games.space_game import SpaceGame
import utils
from settings import Settings

BASE = Path(".")


def list_csv_files(folder):
    return sorted([p.name for p in Path(folder).glob("*.csv")])


def list_music_files(folder):
    exts = (".mp3", ".ogg", ".wav", ".flac")
    return sorted([p.name for p in Path(folder).glob("*") if p.suffix.lower() in exts])


def run_settings_screen(screen, settings: Settings):
    pygame.font.init()
    clock = pygame.time.Clock()
    font = pygame.font.Font(None, 26)
    big = pygame.font.Font(None, 36)
    small = pygame.font.Font(None, 18)

    # ---- constraints & presets ----
    TBQ_MIN_S = 3
    TBQ_MAX_S = 10 * 60
    TOTAL_MIN_MIN = 5
    TOTAL_MAX_MIN = 3 * 60
    LIVES_MIN = 1
    LIVES_MAX = 100

    tbq_presets = [10, 30, 60, 120]  # seconds
    total_presets_min = [5, 15, 30, 60]  # minutes
    lives_presets = [3, 5, 10]

    # ---- helpers ----
    def safe_int(x, default=None):
        try:
            return int(x)
        except Exception:
            return default

    def secs_to_display(secs):
        if secs is None:
            return ("", "s", True)
        s = int(secs)
        if s >= 60 and s % 60 == 0:
            return (str(s // 60), "m", False)
        return (str(s), "s", False)

    def totalsecs_to_display(secs):
        if secs is None:
            return ("", "m", True)
        mins = int(secs // 60)
        if mins >= 60 and mins % 60 == 0:
            return (str(mins // 60), "h", False)
        return (str(mins), "m", False)

    def convert_tbq_digits_on_unit_change(digits, from_unit, to_unit):
        if not digits:
            return ""
        v = safe_int(digits)
        if v is None:
            return ""
        if from_unit == to_unit:
            return str(v)
        if from_unit == "s" and to_unit == "m":
            m = max(1, int(round(v / 60.0)))
            return str(m)
        if from_unit == "m" and to_unit == "s":
            return str(v * 60)
        return str(v)

    def convert_total_digits_on_unit_change(digits, from_unit, to_unit):
        if not digits:
            return ""
        v = safe_int(digits)
        if v is None:
            return ""
        if from_unit == to_unit:
            return str(v)
        if from_unit == "m" and to_unit == "h":
            h = max(1, int(round(v / 60.0)))
            return str(h)
        if from_unit == "h" and to_unit == "m":
            return str(v * 60)
        return str(v)

    def format_manual_display(digits, unit, unlimited):
        if unlimited:
            return "unlimited"
        if digits == "":
            return "<enter>"
        return f"{digits}{unit}"

    # ---- initial values from settings ----
    if getattr(settings, "time_between_questions", None) is None:
        tbq_unlimited = True
        tbq_digits = ""
        tbq_unit = "s"
    else:
        tbq_digits, tbq_unit, tbq_unlimited = secs_to_display(
            int(settings.time_between_questions)
        )

    if getattr(settings, "total_time", None) is None:
        total_unlimited = True
        total_digits = ""
        total_unit = "m"
    else:
        total_digits, total_unit, total_unlimited = totalsecs_to_display(
            int(settings.total_time)
        )

    if getattr(settings, "lives", None) is None:
        lives_unlimited = True
        lives_digits = ""
    else:
        lives_unlimited = False
        lives_digits = str(int(settings.lives))

    # ---- other options (single-column) ----
    opts = [
        (
            "Question order",
            ["top", "bottom", "random"],
            getattr(settings, "question_order"),
        ),
        ("SFX", ["on", "off"], "on" if settings.sfx else "off"),
        ("Music", ["off", "on"], "on" if settings.music else "off"),
        ("Question mode", ["loop", "one_each"], settings.question_mode),
        ("Enemy speed", ["0.75", "1.0", "1.5"], str(settings.enemy_speed_multiplier)),
        ("Muzzle flash", ["on", "off"], "on" if settings.muzzle_flash else "off"),
    ]

    # ---- layout: header + scrollable content + fixed bottom ----
    SCREEN_W, SCREEN_H = screen.get_size()
    LEFT_X = 56
    LABEL_W = 240
    INPUT_X = LEFT_X + LABEL_W + 12
    HEADER_H = 84  # header region (title + help) fixed at top
    BASE_Y = HEADER_H + 24  # content starts below header
    ROW_H = 110
    textbox_w = 180
    unit_w = 44
    chip_h = 28
    bottom_fixed_height = 96

    content_rows = 3 + len(opts)
    content_h = BASE_Y + content_rows * ROW_H + 40
    content_surf = pygame.Surface(
        (SCREEN_W, max(content_h, SCREEN_H - bottom_fixed_height - HEADER_H)),
        flags=pygame.SRCALPHA,
    )
    scroll_y = 0
    content_view_h = SCREEN_H - bottom_fixed_height - HEADER_H
    max_scroll = max(0, content_surf.get_height() - content_view_h)

    running = True
    focused = None  # "tbq","total","lives" or None
    caret_timer = 0
    caret_visible = True
    error_msg = ""
    error_timer = 0

    def set_error(msg, duration=3000):
        nonlocal error_msg, error_timer
        error_msg = msg
        error_timer = duration

    # rect helpers (content coords)
    def row_y(idx):
        # idx=0 -> first row. content_surf top is 0, but we'll place content at BASE_Y on content coords earlier
        return (
            24 + idx * ROW_H
        )  # relative to content_surf coordinate system (content_surf top corresponds to BASE_Y on screen)

    def textbox_rect_for(y):
        return pygame.Rect(INPUT_X, y - 12, textbox_w, 36)

    def unit_rect_for(y, idx):
        return pygame.Rect(
            INPUT_X + textbox_w + 8 + idx * (unit_w + 8), y - 12, unit_w, 36
        )

    def unlimited_rect_for(y):
        return pygame.Rect(INPUT_X + textbox_w + 8 + 2 * (unit_w + 8), y - 12, 100, 36)

    def chips_rect_for(y):
        return pygame.Rect(INPUT_X, y + 36, textbox_w + 200, chip_h + 8)

    # main loop
    while running:
        dt = clock.tick(60)
        caret_timer += dt
        if caret_timer >= 500:
            caret_timer = 0
            caret_visible = not caret_visible

        if error_timer > 0:
            error_timer -= dt
            if error_timer <= 0:
                error_msg = ""

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"

            # scrolling
            if event.type == pygame.MOUSEWHEEL:
                scroll_y -= event.y * 40
                scroll_y = max(0, min(scroll_y, max_scroll))
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button in (4, 5):
                if event.button == 4:
                    scroll_y -= 40
                else:
                    scroll_y += 40
                scroll_y = max(0, min(scroll_y, max_scroll))

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                # fixed bottom Back/Save
                back_rect = utils.button_rect(120, SCREEN_H - 40, w=160, h=48)
                save_rect = utils.button_rect(
                    SCREEN_W - 120, SCREEN_H - 40, w=160, h=48
                )
                if back_rect.collidepoint(mx, my):
                    running = False
                    continue
                if save_rect.collidepoint(mx, my):
                    # validate & save
                    valid = True
                    if tbq_unlimited:
                        settings.time_between_questions = None
                    else:
                        if tbq_digits == "":
                            valid = False
                            set_error(
                                "Time between Qs: enter a number or choose a preset."
                            )
                        else:
                            n = safe_int(tbq_digits)
                            if n is None:
                                valid = False
                                set_error("Time between Qs: invalid number.")
                            else:
                                secs = n if tbq_unit == "s" else n * 60
                                if secs < TBQ_MIN_S or secs > TBQ_MAX_S:
                                    valid = False
                                    set_error(
                                        f"Time between Qs must be {TBQ_MIN_S}s–{TBQ_MAX_S}s."
                                    )
                                else:
                                    settings.time_between_questions = int(secs)
                    if valid:
                        if total_unlimited:
                            settings.total_time = None
                        else:
                            if total_digits == "":
                                valid = False
                                set_error(
                                    "Total time: enter a number or choose a preset."
                                )
                            else:
                                n = safe_int(total_digits)
                                if n is None:
                                    valid = False
                                    set_error("Total time: invalid number.")
                                else:
                                    mins = n if total_unit == "m" else n * 60
                                    if mins < TOTAL_MIN_MIN or mins > TOTAL_MAX_MIN:
                                        valid = False
                                        set_error(
                                            f"Total time must be {TOTAL_MIN_MIN}m–{TOTAL_MAX_MIN}m."
                                        )
                                    else:
                                        settings.total_time = int(mins * 60)
                    if valid:
                        if lives_unlimited:
                            settings.lives = None
                        else:
                            if lives_digits == "":
                                valid = False
                                set_error("Lives: enter a number or choose a preset.")
                            else:
                                n = safe_int(lives_digits)
                                if n is None:
                                    valid = False
                                    set_error("Lives: invalid number.")
                                else:
                                    if n < LIVES_MIN or n > LIVES_MAX:
                                        valid = False
                                        set_error(
                                            f"Lives must be {LIVES_MIN}–{LIVES_MAX}."
                                        )
                                    else:
                                        settings.lives = int(n)
                    if valid:
                        # apply other opts
                        for label, choices, cur in opts:
                            if label == "Question order":
                                settings.question_order = cur
                            elif label == "SFX":
                                settings.sfx = cur == "on"
                            elif label == "Music":
                                settings.music = cur == "on"
                            elif label == "Question mode":
                                settings.question_mode = cur
                            elif label == "Enemy speed":
                                try:
                                    settings.enemy_speed_multiplier = float(cur)
                                except:
                                    settings.enemy_speed_multiplier = 1.0
                            elif label == "Muzzle flash":
                                settings.muzzle_flash = cur == "on"
                        settings.save()
                        running = False
                    continue

                # If click is in header area (title/help) we ignore for content clicks
                if my < HEADER_H:
                    # do nothing (header fixed)
                    continue

                # translate to content coordinates (content_surf coordinates)
                content_x = mx
                content_y = my - HEADER_H + scroll_y

                # row positions within content_surf: row 0 starts at y=24
                def content_row_y(idx):
                    return row_y(idx)

                # TBQ row
                y0 = content_row_y(0)
                tbq_tb = textbox_rect_for(y0)
                tbq_u0 = unit_rect_for(y0, 0)
                tbq_u1 = unit_rect_for(y0, 1)
                tbq_unlim = unlimited_rect_for(y0)
                tbq_chips = chips_rect_for(y0)

                if tbq_tb.collidepoint(content_x, content_y):
                    focused = "tbq"
                elif tbq_u0.collidepoint(content_x, content_y):
                    # set seconds; if not unlimited, convert digits
                    if tbq_unlimited:
                        tbq_unit = "s"
                    else:
                        tbq_digits = convert_tbq_digits_on_unit_change(
                            tbq_digits, tbq_unit, "s"
                        )
                        tbq_unit = "s"
                    focused = "tbq"
                elif tbq_u1.collidepoint(content_x, content_y):
                    if tbq_unlimited:
                        tbq_unit = "m"
                    else:
                        tbq_digits = convert_tbq_digits_on_unit_change(
                            tbq_digits, tbq_unit, "m"
                        )
                        tbq_unit = "m"
                    focused = "tbq"
                elif tbq_unlim.collidepoint(content_x, content_y):
                    tbq_unlimited = not tbq_unlimited
                    if tbq_unlimited:
                        tbq_digits = ""
                    else:
                        tbq_digits = str(max(TBQ_MIN_S, tbq_presets[0]))
                        tbq_unit = "s"
                    focused = "tbq"
                elif tbq_chips.collidepoint(content_x, content_y):
                    cx = tbq_chips.x + 6
                    for p in tbq_presets:
                        chip_rect = pygame.Rect(cx, tbq_chips.y + 6, 64, chip_h)
                        if chip_rect.collidepoint(content_x, content_y):
                            tbq_unlimited = False
                            tbq_unit = "s"
                            tbq_digits = str(p)
                            focused = "tbq"
                            break
                        cx += 72

                # Total row
                y1 = content_row_y(1)
                total_tb = textbox_rect_for(y1)
                total_u0 = unit_rect_for(y1, 0)
                total_u1 = unit_rect_for(y1, 1)
                total_unlim = unlimited_rect_for(y1)
                total_chips = chips_rect_for(y1)

                if total_tb.collidepoint(content_x, content_y):
                    focused = "total"
                elif total_u0.collidepoint(content_x, content_y):
                    if total_unlimited:
                        total_unit = "m"
                    else:
                        total_digits = convert_total_digits_on_unit_change(
                            total_digits, total_unit, "m"
                        )
                        total_unit = "m"
                    focused = "total"
                elif total_u1.collidepoint(content_x, content_y):
                    if total_unlimited:
                        total_unit = "h"
                    else:
                        total_digits = convert_total_digits_on_unit_change(
                            total_digits, total_unit, "h"
                        )
                        total_unit = "h"
                    focused = "total"
                elif total_unlim.collidepoint(content_x, content_y):
                    total_unlimited = not total_unlimited
                    if total_unlimited:
                        total_digits = ""
                    else:
                        total_digits = str(max(TOTAL_MIN_MIN, total_presets_min[0]))
                        total_unit = "m"
                    focused = "total"
                elif total_chips.collidepoint(content_x, content_y):
                    cx = total_chips.x + 6
                    for p in total_presets_min:
                        chip_rect = pygame.Rect(cx, total_chips.y + 6, 64, chip_h)
                        if chip_rect.collidepoint(content_x, content_y):
                            total_unlimited = False
                            total_unit = "m"
                            total_digits = str(p)
                            focused = "total"
                            break
                        cx += 72

                # Lives row
                y2 = content_row_y(2)
                lives_tb = textbox_rect_for(y2)
                lives_unlim_rect = unlimited_rect_for(y2)
                lives_chips = chips_rect_for(y2)

                if lives_tb.collidepoint(content_x, content_y):
                    focused = "lives"
                elif lives_unlim_rect.collidepoint(content_x, content_y):
                    lives_unlimited = not lives_unlimited
                    if lives_unlimited:
                        lives_digits = ""
                    else:
                        lives_digits = str(max(LIVES_MIN, lives_presets[0]))
                    focused = "lives"
                elif lives_chips.collidepoint(content_x, content_y):
                    cx = lives_chips.x + 6
                    for p in lives_presets:
                        chip_rect = pygame.Rect(cx, lives_chips.y + 6, 64, chip_h)
                        if chip_rect.collidepoint(content_x, content_y):
                            lives_unlimited = False
                            lives_digits = str(p)
                            focused = "lives"
                            break
                        cx += 72

                # remaining options matrix (single-column below manual rows)
                for i, (label, choices, cur) in enumerate(opts):
                    ry = content_row_y(3 + i)
                    val_rect = pygame.Rect(INPUT_X, ry - 12, textbox_w + 120, 36)
                    if val_rect.collidepoint(content_x, content_y):
                        try:
                            idx = choices.index(cur)
                        except ValueError:
                            idx = 0
                        idx = (idx + 1) % len(choices)
                        opts[i] = (label, choices, choices[idx])
                        break

            if event.type == pygame.KEYDOWN:
                if focused == "tbq":
                    if event.key == pygame.K_ESCAPE:
                        focused = None
                    elif event.key == pygame.K_BACKSPACE:
                        tbq_digits = tbq_digits[:-1]
                        if tbq_digits == "":
                            tbq_unlimited = True
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        focused = None
                    else:
                        ch = event.unicode
                        if ch.isdigit():
                            tbq_unlimited = False
                            if len(tbq_digits) < 6:
                                tbq_digits = (tbq_digits + ch).lstrip("0") or ch
                elif focused == "total":
                    if event.key == pygame.K_ESCAPE:
                        focused = None
                    elif event.key == pygame.K_BACKSPACE:
                        total_digits = total_digits[:-1]
                        if total_digits == "":
                            total_unlimited = True
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        focused = None
                    else:
                        ch = event.unicode
                        if ch.isdigit():
                            total_unlimited = False
                            if len(total_digits) < 6:
                                total_digits = (total_digits + ch).lstrip("0") or ch
                elif focused == "lives":
                    if event.key == pygame.K_ESCAPE:
                        focused = None
                    elif event.key == pygame.K_BACKSPACE:
                        lives_digits = lives_digits[:-1]
                        if lives_digits == "":
                            lives_unlimited = True
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        focused = None
                    else:
                        ch = event.unicode
                        if ch.isdigit():
                            lives_unlimited = False
                            if len(lives_digits) < 3:
                                lives_digits = (lives_digits + ch).lstrip("0") or ch
                else:
                    if event.key == pygame.K_ESCAPE:
                        running = False

        # ---- draw header (fixed) ----
        screen.fill((18, 18, 28))
        title = big.render("Settings", True, (255, 255, 255))
        screen.blit(title, (SCREEN_W // 2 - title.get_width() // 2, 12))
        # help text placed under title and fixed
        help_text = "Click an input to edit; units convert; chips = quick presets."
        help_surf = small.render(help_text, True, (170, 170, 190))
        screen.blit(help_surf, (SCREEN_W // 2 - help_surf.get_width() // 2, 48))

        # ---- draw content onto content_surf ----
        content_surf.fill((22, 22, 34))

        # content starts with a small header area so row_y(0) looks nice
        # draw rows in content_surf's coordinate system where top y=0 corresponds to BASE_Y on screen
        def draw_manual_row(
            surface,
            label_text,
            idx,
            digits,
            unit,
            unlimited,
            focused_name,
            unit_labels,
            chips,
        ):
            y = row_y(idx)
            surface.blit(font.render(label_text, True, (210, 210, 210)), (LEFT_X, y))
            tb = textbox_rect_for(y)
            pygame.draw.rect(surface, (38, 38, 58), tb, border_radius=8)
            # focus outline
            if focused == focused_name:
                pygame.draw.rect(surface, (100, 140, 200), tb, width=2, border_radius=8)
            # display
            disp = format_manual_display(digits, unit, unlimited)
            caret = (
                "▌"
                if (focused == focused_name and caret_visible and disp != "unlimited")
                else ""
            )
            surface.blit(
                font.render(disp + caret, True, (180, 180, 255)), (tb.x + 8, tb.y + 6)
            )
            # unit buttons: draw highlight *behind* text so letters remain visible
            u0 = unit_rect_for(y, 0)
            u1 = unit_rect_for(y, 1)
            # base
            pygame.draw.rect(surface, (56, 56, 86), u0, border_radius=6)
            pygame.draw.rect(surface, (56, 56, 86), u1, border_radius=6)
            # highlight if active (draw filled then text on top)
            if not unlimited:
                if unit == unit_labels[0]:
                    pygame.draw.rect(surface, (100, 140, 200), u0, border_radius=6)
                else:
                    pygame.draw.rect(surface, (100, 140, 200), u1, border_radius=6)
            # write unit letters on top
            surface.blit(
                small.render(unit_labels[0], True, (255, 255, 255)),
                (u0.x + 12, u0.y + 8),
            )
            surface.blit(
                small.render(unit_labels[1], True, (255, 255, 255)),
                (u1.x + 12, u1.y + 8),
            )
            # unlimited toggle: draw highlight behind text if enabled
            unlim = unlimited_rect_for(y)
            if unlimited:
                pygame.draw.rect(surface, (100, 140, 200), unlim, border_radius=6)
            else:
                pygame.draw.rect(surface, (72, 72, 96), unlim, border_radius=6)
            surface.blit(
                font.render("Unlimited", True, (240, 240, 240)),
                (unlim.x + 10, unlim.y + 6),
            )
            # chips row
            chips_r = chips_rect_for(y)
            cx = chips_r.x + 6
            for p in chips:
                chip_rect = pygame.Rect(cx, chips_r.y + 6, 64, chip_h)
                pygame.draw.rect(surface, (56, 56, 86), chip_rect, border_radius=6)
                label = f"{p}{unit_labels[0] if label_text=='Time between Qs' else 'm' if label_text=='Total time' else ''}"
                if label_text == "Time between Qs":
                    cap = small.render(f"{p}s", True, (220, 220, 255))
                elif label_text == "Total time":
                    cap = small.render(f"{p}m", True, (220, 220, 255))
                else:
                    cap = small.render(str(p), True, (220, 220, 255))
                surface.blit(
                    cap,
                    (
                        chip_rect.x + (chip_rect.w - cap.get_width()) // 2,
                        chip_rect.y + 6,
                    ),
                )
                cx += chip_rect.w + 8

        # draw manual rows
        draw_manual_row(
            content_surf,
            "Time between Qs",
            0,
            tbq_digits,
            tbq_unit,
            tbq_unlimited,
            "tbq",
            ("s", "m"),
            tbq_presets,
        )
        draw_manual_row(
            content_surf,
            "Total time",
            1,
            total_digits,
            total_unit,
            total_unlimited,
            "total",
            ("m", "h"),
            total_presets_min,
        )
        # Lives (no unit labels)
        y = row_y(2)
        content_surf.blit(font.render("Lives", True, (210, 210, 210)), (LEFT_X, y))
        tb = textbox_rect_for(y)
        pygame.draw.rect(content_surf, (38, 38, 58), tb, border_radius=8)
        if focused == "lives":
            pygame.draw.rect(
                content_surf, (100, 140, 200), tb, width=2, border_radius=8
            )
        disp_l = (
            "unlimited"
            if lives_unlimited
            else (lives_digits if lives_digits != "" else "<enter>")
        )
        if focused == "lives" and caret_visible and disp_l != "unlimited":
            disp_l += "▌"
        content_surf.blit(
            font.render(disp_l, True, (180, 180, 255)), (tb.x + 8, tb.y + 6)
        )
        unlim_l = unlimited_rect_for(y)
        if lives_unlimited:
            pygame.draw.rect(content_surf, (100, 140, 200), unlim_l, border_radius=6)
        else:
            pygame.draw.rect(content_surf, (72, 72, 96), unlim_l, border_radius=6)
        content_surf.blit(
            font.render("Unlimited", True, (240, 240, 240)),
            (unlim_l.x + 10, unlim_l.y + 6),
        )
        chips_r = chips_rect_for(y)
        cx = chips_r.x + 6
        for p in lives_presets:
            chip_rect = pygame.Rect(cx, chips_r.y + 6, 64, chip_h)
            pygame.draw.rect(content_surf, (56, 56, 86), chip_rect, border_radius=6)
            cap = small.render(str(p), True, (220, 220, 255))
            content_surf.blit(
                cap,
                (chip_rect.x + (chip_rect.w - cap.get_width()) // 2, chip_rect.y + 6),
            )
            cx += chip_rect.w + 8

        # draw remaining options in same column, below manual rows
        for i, (label, choices, cur) in enumerate(opts):
            ry = row_y(3 + i)
            content_surf.blit(font.render(label, True, (210, 210, 210)), (LEFT_X, ry))
            val_rect = pygame.Rect(INPUT_X, ry - 12, textbox_w + 120, 36)
            pygame.draw.rect(content_surf, (38, 38, 58), val_rect, border_radius=8)
            content_surf.blit(
                font.render(str(cur), True, (180, 180, 255)),
                (val_rect.x + 8, val_rect.y + 6),
            )
            content_surf.blit(
                small.render("(click to cycle)", True, (120, 120, 120)),
                (val_rect.right + 8, ry + 6),
            )

        # blit the content_surf at fixed position below header, applying scroll
        screen.blit(
            content_surf,
            (0, HEADER_H),
            area=pygame.Rect(0, scroll_y, SCREEN_W, content_view_h),
        )

        # help text already drawn in header above; draw error area (fixed above bottom buttons)
        if error_msg:
            em = font.render(error_msg, True, (255, 100, 100))
            screen.blit(em, (LEFT_X, SCREEN_H - bottom_fixed_height + 12))

        # bottom fixed Back/Save
        back = utils.button_rect(120, SCREEN_H - 40, w=160, h=48)
        pygame.draw.rect(screen, (80, 80, 120), back, border_radius=10)
        screen.blit(
            font.render("Back", True, (255, 255, 255)), (back.x + 40, back.y + 12)
        )
        save = utils.button_rect(SCREEN_W - 120, SCREEN_H - 40, w=160, h=48)
        pygame.draw.rect(screen, (50, 150, 80), save, border_radius=10)
        screen.blit(
            font.render("Save", True, (255, 255, 255)), (save.x + 56, save.y + 12)
        )

        pygame.display.flip()

    return "ok"


def run_menu():
    pygame.init()
    screen = pygame.display.set_mode((800, 600))
    pygame.display.set_caption("Study Gamify - Main Menu")
    clock = pygame.time.Clock()
    font = pygame.font.Font(None, 28)
    big = pygame.font.Font(None, 40)

    # load or create settings
    settings = Settings.load()

    # default question file (try questions.csv)
    selected_csv = None
    csvs = list_csv_files(".")
    if "questions.csv" in csvs:
        selected_csv = "questions.csv"
    elif csvs:
        selected_csv = csvs[0]

    while True:
        dt = clock.tick(60)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit(0)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                play_rect = utils.button_rect(400, 170, w=360, h=60)
                file_rect = utils.button_rect(400, 260, w=360, h=50)
                settings_rect = utils.button_rect(400, 350, w=360, h=50)
                quit_rect = utils.button_rect(400, 450, w=200, h=44)
                if play_rect.collidepoint(mx, my):
                    if selected_csv is None:
                        print("Choose a question CSV first.")
                    else:
                        game = SpaceGame(selected_csv, settings=settings)
                        game.load_sounds(".")  # load sounds from current folder
                        result = game.run()
                        csvs = list_csv_files(".")
                elif file_rect.collidepoint(mx, my):
                    csvs = list_csv_files(".")
                    if not csvs:
                        selected_csv = None
                    else:
                        if selected_csv is None:
                            selected_csv = csvs[0]
                        else:
                            try:
                                idx = csvs.index(selected_csv)
                                idx = (idx + 1) % len(csvs)
                                selected_csv = csvs[idx]
                            except ValueError:
                                selected_csv = csvs[0]
                elif settings_rect.collidepoint(mx, my):
                    run_settings_screen(screen, settings)
                elif quit_rect.collidepoint(mx, my):
                    pygame.quit()
                    sys.exit(0)

        screen.fill((18, 18, 28))
        title = big.render("Study Gamify", True, (255, 255, 255))
        screen.blit(title, (400 - title.get_width() // 2, 30))

        # draw buttons
        play_rect = utils.button_rect(400, 170, w=360, h=60)
        pygame.draw.rect(screen, (60, 120, 180), play_rect, border_radius=8)
        screen.blit(
            font.render("Play: Space Invaders (Study Mode)", True, (255, 255, 255)),
            (play_rect.x + 14, play_rect.y + 18),
        )

        file_rect = utils.button_rect(400, 260, w=360, h=50)
        pygame.draw.rect(screen, (90, 90, 90), file_rect, border_radius=8)
        file_text = (
            selected_csv if selected_csv else "No CSV found. Drop questions.csv here."
        )
        screen.blit(
            font.render(f"Questions file: {file_text}", True, (255, 255, 255)),
            (file_rect.x + 14, file_rect.y + 14),
        )

        settings_rect = utils.button_rect(400, 350, w=360, h=50)
        pygame.draw.rect(screen, (100, 90, 140), settings_rect, border_radius=8)
        screen.blit(
            font.render("Settings", True, (255, 255, 255)),
            (settings_rect.x + 14, settings_rect.y + 14),
        )

        csvs = list_csv_files(".")
        quit_rect = utils.button_rect(400, 450, w=200, h=44)
        pygame.draw.rect(screen, (120, 60, 80), quit_rect, border_radius=8)
        screen.blit(
            font.render("Quit", True, (255, 255, 255)),
            (quit_rect.x + 64, quit_rect.y + 10),
        )

        hint = font.render(
            "Click 'Questions file' to cycle CSVs in this folder.",
            True,
            (180, 180, 180),
        )
        screen.blit(hint, (400 - hint.get_width() // 2, 520))

        pygame.display.flip()


if __name__ == "__main__":
    run_menu()
