#!/usr/bin/env python3
"""Render the v2 one-page newspaper image (1024x1024 PNG) from stories.json.

v2 rebuilds the 21 Nov page as an illustrated front page following the
winners' design (see the 22 Nov v4 page): date masthead, numbers strip,
region colour bar, dark UTC strip, 3 big illustrated stories + 12 small
illustrated stories (flat PIL vector, one accent colour per scene), a red
topic bar on every illustration with the story's main topic in short white
caps (rank 1 style), numbered stories with CONFIRMED/OFFICIAL/REPORTED/
CLAIM badge chips + per-story sources, ALSO ON list, world map with
numbered pins, DATE CHECK box, footer with tag legend.

Fixes vs v1: the 4 wrong-date stories are replaced (Polish airspace was
Fri 20 Nov, Shenzhen summit and Myanmar ICJ ruling were Thu 19 Nov, the
Ethiopia displacement was reported 22 Nov); no summary is truncated — the
renderer prints a TRUNCATED warning for any headline/summary that wraps
past its line budget; v2 renders with none.

All text is real, legible type (DejaVu) -- no generated imagery.

Usage: python3 render.py stories.json news-20261121-v2.png
"""
import json
import math
import sys
import os
from PIL import Image, ImageDraw, ImageFont

W, H = 1024, 1024
BG = (248, 244, 232)
INK = (17, 17, 17)
RED = (163, 18, 18)
SALMON = (232, 110, 100)
MUTED = (90, 84, 70)
RULE = (60, 55, 45)
LIGHT = (226, 219, 198)
NAVY = (24, 32, 56)
MAP_LAND = (206, 214, 196)
MAP_LINE = (120, 118, 108)

BADGE = {
    "CONFIRMED": (46, 125, 50),
    "OFFICIAL": (29, 78, 216),
    "REPORTED": (55, 65, 81),
    "CLAIM": (180, 83, 9),
    "FORECAST": (107, 114, 128),
    "PENDING": (29, 78, 216),
}

SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
SERIF_B = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
SERIF_I = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf"
SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
SANS_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def font(path, size, fallback=None):
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.truetype(fallback or SERIF, size)


def wrap(draw, text, fnt, max_w):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=fnt) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def draw_wrapped(draw, x, y, lines, fnt, fill, lh):
    for ln in lines:
        draw.text((x, y), ln, font=fnt, fill=fill)
        y += lh
    return y


def chip(d, x_right, y, text, size=9):
    """Badge chip, right-aligned at x_right. Returns its left edge."""
    f = font(SANS_B, size)
    tw = d.textlength(text, font=f)
    pad_x, pad_y = 5, 2
    h = size + 2 * pad_y + 3
    x0 = x_right - int(tw) - 2 * pad_x
    d.rounded_rectangle([x0, y, x_right, y + h], radius=3,
                        fill=BADGE.get(text, (55, 65, 81)))
    d.text((x0 + pad_x, y + pad_y), text, font=f, fill=(255, 255, 255))
    return x0


def redbar(d, x, y, size, text, h=16, max_w=None):
    """Red topic bar at the top-left of an illustration (rank 1 style).

    White bold caps text centred in a red rectangle; the font shrinks
    until the bar fits max_w. Returns the bar width in pixels.
    """
    f = font(SANS_B, size)
    while max_w is not None and d.textlength(text, font=f) + 12 > max_w and f.size > 6:
        f = font(SANS_B, f.size - 1)
    tw = d.textlength(text, font=f)
    bw = int(tw) + 12
    d.rectangle([x, y, x + bw, y + h], fill=RED)
    d.text((x + 6, y + (h - f.size) // 2 - 1), text, font=f, fill=(255, 255, 255))
    return bw


def whitebar(d, x_right, y, size, text, h=16):
    """White secondary bar at the top-right of a big illustration.

    Dark bold caps text centred in a white rectangle. Returns the bar
    width in pixels.
    """
    f = font(SANS_B, size)
    tw = d.textlength(text, font=f)
    bw = int(tw) + 12
    d.rectangle([x_right - bw, y, x_right, y + h], fill=(255, 255, 255))
    d.text((x_right - bw + 6, y + (h - f.size) // 2 - 1), text, font=f,
           fill=(30, 30, 40))
    return bw


# Rough continent outlines (lon, lat) for the WHERE IT HAPPENED map.
CONTINENTS = [
    [(-168, 66), (-140, 70), (-125, 72), (-110, 73), (-95, 80), (-85, 66), (-75, 62), (-65, 60), (-55, 52), (-60, 47), (-70, 44), (-75, 40), (-80, 32), (-85, 30), (-90, 21), (-95, 19), (-100, 16), (-105, 20), (-110, 23), (-115, 30), (-125, 40), (-125, 49), (-135, 58), (-150, 60), (-165, 60)],
    [(-80, 10), (-75, 7), (-65, 5), (-55, 5), (-50, 0), (-40, -5), (-35, -10), (-40, -20), (-48, -28), (-55, -35), (-65, -45), (-70, -55), (-73, -40), (-72, -20), (-78, -5)],
    [(-10, 36), (-5, 44), (0, 50), (5, 55), (10, 58), (18, 56), (20, 60), (25, 65), (30, 70), (35, 68), (40, 60), (30, 55), (25, 50), (20, 45), (15, 44), (10, 38), (0, 36)],
    [(-10, 35), (0, 36), (10, 37), (20, 32), (30, 31), (35, 28), (40, 20), (48, 11), (51, 10), (45, 0), (40, -10), (35, -20), (30, -30), (20, -35), (15, -28), (12, -18), (10, -5), (5, 5), (-5, 5), (-10, 15), (-15, 25)],
    [(35, 68), (50, 70), (70, 72), (100, 75), (130, 72), (160, 70), (178, 65), (170, 60), (160, 55), (140, 50), (135, 45), (130, 35), (125, 30), (120, 25), (110, 20), (105, 10), (100, 8), (95, 15), (90, 22), (85, 20), (80, 10), (75, 8), (70, 25), (60, 25), (55, 28), (50, 30), (45, 35), (40, 38)],
    [(113, -22), (120, -15), (130, -12), (135, -15), (140, -17), (145, -15), (150, -22), (153, -28), (150, -37), (145, -38), (140, -38), (135, -35), (130, -32), (125, -32), (120, -35), (115, -33), (113, -25)],
]


# ---------------------------------------------------------------- scenes
def scene_cop31(d, x, y, w, h):
    """Antalya at dawn: navy-to-orange sky bands, sun with rays, purple
    mountains, skyline with lit windows, sea with reflection lines."""
    d.rectangle([x, y, x + w, y + int(h * 0.38)], fill=(38, 44, 78))
    d.rectangle([x, y + int(h * 0.38), x + w, y + int(h * 0.66)], fill=(214, 106, 59))
    d.rectangle([x, y + int(h * 0.66), x + w, y + int(h * 0.82)], fill=(240, 180, 90))
    # purple mountain silhouettes behind the skyline
    d.polygon([(x, y + int(h * 0.82)), (x + int(w * 0.22), y + int(h * 0.52)),
               (x + int(w * 0.45), y + int(h * 0.82))], fill=(90, 60, 110))
    d.polygon([(x + int(w * 0.55), y + int(h * 0.82)), (x + int(w * 0.78), y + int(h * 0.58)),
               (x + w, y + int(h * 0.82))], fill=(90, 60, 110))
    # sun with short rays
    cx, cy, r = x + int(w * 0.62), y + int(h * 0.52), int(h * 0.15)
    for ang in range(0, 360, 30):
        ex1 = cx + int((r + 8) * math.cos(math.radians(ang)))
        ey1 = cy + int((r + 8) * math.sin(math.radians(ang)))
        ex2 = cx + int((r + 16) * math.cos(math.radians(ang)))
        ey2 = cy + int((r + 16) * math.sin(math.radians(ang)))
        d.line([(ex1, ey1), (ex2, ey2)], fill=(250, 214, 140), width=2)
    d.ellipse([cx - r - 5, cy - r - 5, cx + r + 5, cy + r + 5], fill=(250, 214, 140))
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 233, 168))
    # two birds, clear of the red topic bar (top-left) and the white bar
    for bx, by in [(0.18, 0.22), (0.45, 0.12)]:
        px, py = x + int(w * bx), y + int(h * by)
        d.line([(px - 5, py), (px, py - 3), (px + 5, py)], fill=(30, 30, 40), width=2)
    base = y + int(h * 0.82)
    skyline = [(0, 0.42), (0.10, 0.55), (0.20, 0.34), (0.30, 0.50), (0.40, 0.30),
               (0.50, 0.52), (0.60, 0.38), (0.70, 0.56), (0.80, 0.34), (0.90, 0.48)]
    for fx, fh in skyline:
        bx = x + int(w * fx)
        bw = max(8, int(w * 0.09))
        d.rectangle([bx, base - int(h * fh), bx + bw, base], fill=(28, 28, 34))
        for wy in range(3):
            d.rectangle([bx + 3, base - int(h * fh) + 5 + wy * 9, bx + 6,
                         base - int(h * fh) + 8 + wy * 9], fill=(255, 214, 110))
    d.rectangle([x, base, x + w, y + h], fill=(31, 58, 95))
    d.line([(x + 10, base + 5), (x + w - 40, base + 5)], fill=(150, 190, 220), width=1)
    d.line([(x + 40, base + 11), (x + w - 10, base + 11)], fill=(150, 190, 220), width=1)
    d.line([(x + 70, base + 16), (x + w - 60, base + 16)], fill=(150, 190, 220), width=1)


def scene_bahrain(d, x, y, w, h):
    """Bahrain at night: radar blocks burning with smoke, sea with
    reflection dashes, ship with containers and bridge, missile arc
    with an orange flash at its end."""
    d.rectangle([x, y, x + w, y + h], fill=(18, 26, 52))
    for sx, sy in [(0.10, 0.12), (0.30, 0.08), (0.55, 0.14), (0.75, 0.08), (0.90, 0.18)]:
        d.ellipse([x + int(w * sx) - 1, y + int(h * sy) - 1,
                   x + int(w * sx) + 1, y + int(h * sy) + 1], fill=(255, 255, 255))
    sea = y + int(h * 0.70)
    d.rectangle([x, sea, x + w, y + h], fill=(28, 68, 110))
    # two radar/industrial blocks with flames and smoke clouds
    for fx, fw in [(0.08, 0.20), (0.38, 0.20)]:
        bx, bw = x + int(w * fx), int(w * fw)
        d.rectangle([bx, sea - 34, bx + bw, sea], fill=(125, 130, 140))
        d.ellipse([bx + bw // 2 - 10, sea - 46, bx + bw // 2 + 10, sea - 30],
                  fill=(150, 155, 165))
        cxm = bx + bw // 2
        # flames, tips lowered to stay clear of the red topic bar
        d.polygon([(cxm - 12, sea - 36), (cxm + 12, sea - 36),
                   (cxm, sea - 48)], fill=(255, 140, 40))
        d.polygon([(cxm - 6, sea - 36), (cxm + 6, sea - 36),
                   (cxm, sea - 42)], fill=(255, 214, 110))
        # grey smoke clouds drifting right of the flames
        d.ellipse([cxm + 8, sea - 52, cxm + 28, sea - 42], fill=(120, 125, 135))
        d.ellipse([cxm + 20, sea - 58, cxm + 38, sea - 48], fill=(140, 145, 155))
        # sea reflection dashes under the flames
        d.line([(bx + 4, sea + 6), (bx + bw - 4, sea + 6)], fill=(255, 160, 60), width=2)
        d.line([(bx + 10, sea + 12), (bx + bw - 10, sea + 12)], fill=(255, 160, 60), width=1)
    # ship on the right: hull, containers, bridge block
    sx0 = x + int(w * 0.68)
    d.polygon([(sx0, sea + 4), (sx0 + int(w * 0.24), sea + 4),
               (sx0 + int(w * 0.20), sea + 14), (sx0 + 6, sea + 14)], fill=(20, 20, 28))
    d.rectangle([sx0 + 10, sea - 6, sx0 + 34, sea + 4], fill=(150, 60, 50))
    d.rectangle([sx0 + 38, sea - 6, sx0 + 58, sea + 4], fill=(70, 110, 160))
    d.rectangle([sx0 + 62, sea - 6, sx0 + 82, sea + 4], fill=(150, 150, 140))
    d.rectangle([sx0 + 66, sea - 18, sx0 + 82, sea - 6], fill=(220, 220, 210))
    d.rectangle([sx0 + 69, sea - 15, sx0 + 79, sea - 11], fill=(40, 80, 120))
    # two ship wake lines
    d.line([(sx0 - 20, sea + 16), (sx0 + int(w * 0.24), sea + 16)],
           fill=(150, 190, 220), width=1)
    d.line([(sx0 - 34, sea + 22), (sx0 + int(w * 0.20), sea + 22)],
           fill=(150, 190, 220), width=1)
    # dotted missile arc, starting below the red topic bar, with an
    # orange flash at its end
    for k in range(7):
        t = k / 6.0
        ax = x + int(w * (0.05 + 0.35 * t))
        ay = y + int(h * (0.16 + 0.22 * t * t))
        d.ellipse([ax - 2, ay - 2, ax + 2, ay + 2], fill=(255, 255, 255))
    fxe, fye = x + int(w * 0.40), y + int(h * 0.38)
    d.ellipse([fxe - 6, fye - 6, fxe + 6, fye + 6], fill=(255, 140, 40))


def scene_sparta(d, x, y, w, h):
    """Sparta II at dawn in the Gulf of Finland: dark sky, stars, two
    drones with dotted trails, a cargo ship with containers burning on
    deck, grey smoke drifting right, cold sea with wave arcs."""
    d.rectangle([x, y, x + w, y + h], fill=(16, 22, 44))
    for sx, sy in [(0.06, 0.10), (0.20, 0.06), (0.34, 0.12), (0.48, 0.08),
                   (0.62, 0.12), (0.78, 0.06), (0.90, 0.12), (0.55, 0.20)]:
        d.ellipse([x + int(w * sx) - 1, y + int(h * sy) - 1,
                   x + int(w * sx) + 1, y + int(h * sy) + 1], fill=(255, 255, 255))
    sea = y + int(h * 0.68)
    d.rectangle([x, sea, x + w, y + h], fill=(28, 68, 110))
    # white wave arcs on the sea
    for wx, wy in [(0.05, 0.78), (0.30, 0.84), (0.60, 0.78), (0.82, 0.86)]:
        ax0, ay0 = x + int(w * wx), y + int(h * wy)
        d.arc([ax0, ay0, ax0 + 46, ay0 + 14], start=180, end=360,
              fill=(200, 220, 240), width=2)
    # cargo ship: long hull, three coloured containers, bridge block
    hx0 = x + int(w * 0.10)
    hx1 = x + int(w * 0.88)
    d.polygon([(hx0, sea - 6), (hx1, sea - 6), (hx1 - 14, sea + 12),
               (hx0 + 10, sea + 12)], fill=(20, 20, 28))
    d.rectangle([hx0 + 22, sea - 22, hx0 + 62, sea - 6], fill=(180, 60, 50))
    d.rectangle([hx0 + 66, sea - 22, hx0 + 106, sea - 6], fill=(70, 110, 160))
    d.rectangle([hx0 + 110, sea - 22, hx0 + 146, sea - 6], fill=(150, 150, 140))
    d.rectangle([hx0 + 150, sea - 38, hx0 + 172, sea - 22], fill=(220, 220, 210))
    d.rectangle([hx0 + 154, sea - 34, hx0 + 168, sea - 28], fill=(40, 80, 120))
    # flames on the deck between the containers, tips below the bars
    for fx, fw, fh in [(0.30, 0.06, 0.34), (0.42, 0.05, 0.28), (0.52, 0.06, 0.30)]:
        bx = x + int(w * fx)
        d.polygon([(bx, sea - 22), (bx + int(w * fw), sea - 22),
                   (bx + int(w * fw) // 2, sea - 22 - int(h * fh))], fill=(255, 140, 40))
        d.polygon([(bx + 4, sea - 22), (bx + int(w * fw) - 4, sea - 22),
                   (bx + int(w * fw) // 2, sea - 22 - int(h * fh) + 8)],
                  fill=(255, 214, 110))
    # grey smoke clouds drifting right of the flames
    for sx, sy, sw in [(0.55, 0.30, 34), (0.62, 0.24, 40), (0.70, 0.30, 30)]:
        d.ellipse([x + int(w * sx), y + int(h * sy),
                   x + int(w * sx) + sw, y + int(h * sy) + 12], fill=(140, 145, 155))
    # two drones with dotted trails, clear of the bars
    for dx, dy, s in [(0.82, 0.24, 7), (0.70, 0.42, 6)]:
        cx, cy = x + int(w * dx), y + int(h * dy)
        d.line([(cx - s, cy - s), (cx + s, cy + s)], fill=(255, 220, 130), width=2)
        d.line([(cx - s, cy + s), (cx + s, cy - s)], fill=(255, 220, 130), width=2)
        for k in range(1, 4):
            d.ellipse([cx - s - k * 9 - 1, cy + k * 4 - 1,
                       cx - s - k * 9 + 1, cy + k * 4 + 1], fill=(255, 220, 130))
    # orange reflection dashes under the flames
    d.line([(hx0 + 30, sea + 16), (hx0 + 150, sea + 16)], fill=(255, 160, 60), width=2)
    d.line([(hx0 + 50, sea + 22), (hx0 + 130, sea + 22)], fill=(255, 160, 60), width=1)


def _small_bg(d, x, y, w, h, color):
    d.rectangle([x, y, x + w, y + h], fill=color)


def scene_boat(d, x, y, w, h):
    _small_bg(d, x, y, w, h, (70, 120, 170))
    # green bank with two trees, below the red topic bar
    d.rectangle([x, y, x + 24, y + h], fill=(90, 140, 70))
    for tx, ty in [(10, 24), (18, 32)]:
        d.ellipse([x + tx - 4, y + ty, x + tx + 6, y + ty + 10], fill=(50, 110, 50))
        d.line([(x + tx + 1, y + ty + 10), (x + tx + 1, y + ty + 16)], fill=(90, 60, 30), width=2)
    # river with white wave arcs
    d.rectangle([x + 24, y + 34, x + w, y + h], fill=(30, 80, 130))
    d.arc([x + 30, y + 38, x + 70, y + 50], start=180, end=360, fill=(255, 255, 255), width=2)
    d.arc([x + 96, y + 40, x + 140, y + 52], start=180, end=360, fill=(255, 255, 255), width=2)
    # tilted wooden boat with three passenger dots
    d.polygon([(x + 44, y + 18), (x + 112, y + 28), (x + 100, y + 40), (x + 52, y + 32)],
              fill=(120, 85, 50))
    for px, py in [(66, 10), (84, 14), (96, 18)]:
        d.ellipse([x + px, y + py, x + px + 6, y + py + 6], fill=(40, 40, 40))
    # orange lifebuoy ring
    d.ellipse([x + 118, y + 12, x + 134, y + 28], outline=(255, 140, 40), width=3)
    d.ellipse([x + 122, y + 16, x + 130, y + 24], outline=(255, 140, 40), width=2)
    # small rescue boat approaching from the right
    d.polygon([(x + 116, y + 38), (x + 146, y + 38), (x + 140, y + 46), (x + 122, y + 46)],
              fill=(200, 60, 40))
    d.rectangle([x + 126, y + 32, x + 136, y + 38], fill=(255, 255, 255))


def scene_hospital(d, x, y, w, h):
    _small_bg(d, x, y, w, h, (235, 235, 228))
    d.rectangle([x, y + 40, x + w, y + h], fill=(120, 170, 90))
    # white hospital building with a red cross sign and lit windows
    d.rectangle([x + 40, y + 12, x + 112, y + 40], fill=(255, 255, 255),
                outline=(60, 55, 45), width=2)
    d.rectangle([x + 70, y + 16, x + 78, y + 32], fill=(200, 30, 30))
    d.rectangle([x + 64, y + 22, x + 84, y + 28], fill=(200, 30, 30))
    for wx in (48, 90):
        d.rectangle([x + wx, y + 18, x + wx + 8, y + 26], fill=(120, 170, 200))
    # white ambulance with a red cross on the lawn
    d.rectangle([x + 116, y + 34, x + 148, y + 46], fill=(255, 255, 255),
                outline=(60, 55, 45), width=1)
    d.rectangle([x + 128, y + 37, x + 132, y + 43], fill=(200, 30, 30))
    d.rectangle([x + 125, y + 39, x + 135, y + 41], fill=(200, 30, 30))
    d.ellipse([x + 120, y + 44, x + 126, y + 50], fill=(20, 20, 20))
    d.ellipse([x + 138, y + 44, x + 144, y + 50], fill=(20, 20, 20))
    # red ECG line across the bottom
    d.line([(x + 6, y + 50), (x + 20, y + 50), (x + 24, y + 44), (x + 28, y + 52),
            (x + 32, y + 47), (x + 36, y + 50), (x + 60, y + 50)], fill=(200, 30, 30), width=2)


def scene_basket(d, x, y, w, h):
    _small_bg(d, x, y, w, h, (222, 160, 90))
    # court lines and centre circle
    d.line([(x, y + 40), (x + w, y + 40)], fill=(255, 255, 255), width=2)
    d.ellipse([x + 52, y + 26, x + 100, y + 54], outline=(255, 255, 255), width=2)
    # crowd strip along the bottom
    d.rectangle([x, y + 48, x + w, y + h], fill=(120, 70, 40))
    for cx in range(4, w - 4, 10):
        d.ellipse([x + cx, y + 49, x + cx + 5, y + 53],
                  fill=(255, 220, 180) if cx % 20 == 4 else (240, 200, 160))
    # hoop: backboard and rim on the right
    d.rectangle([x + 142, y + 8, x + 148, y + 30], fill=(255, 255, 255),
                outline=(60, 55, 45), width=1)
    d.ellipse([x + 132, y + 28, x + 144, y + 36], outline=(200, 60, 20), width=2)
    d.line([(x + 134, y + 36), (x + 138, y + 44)], fill=(255, 255, 255), width=1)
    d.line([(x + 142, y + 36), (x + 138, y + 44)], fill=(255, 255, 255), width=1)
    # orange ball mid-air
    d.ellipse([x + 108, y + 10, x + 132, y + 34], fill=(230, 110, 30),
              outline=(120, 60, 10), width=2)
    d.arc([x + 108, y + 10, x + 132, y + 34], start=200, end=340, fill=(120, 60, 10), width=2)
    d.line([(x + 120, y + 10), (x + 120, y + 34)], fill=(120, 60, 10), width=2)
    # jumping player silhouette
    d.ellipse([x + 60, y + 18, x + 68, y + 26], fill=(40, 40, 40))
    d.polygon([(x + 62, y + 26), (x + 68, y + 26), (x + 72, y + 42), (x + 58, y + 42)],
              fill=(40, 40, 40))
    d.line([(x + 66, y + 28), (x + 78, y + 18)], fill=(40, 40, 40), width=3)


def scene_fbi(d, x, y, w, h):
    _small_bg(d, x, y, w, h, (52, 68, 96))
    # grid of small light rectangles (data rows)
    for r in range(3):
        for c in range(4):
            d.rectangle([x + 10 + c * 13, y + 10 + r * 12, x + 20 + c * 13, y + 19 + r * 12],
                        fill=(160, 180, 210) if (r + c) % 3 else (220, 230, 245))
    # fingerprint: concentric arcs in yellow
    cx, cy = x + 104, y + 24
    for rr in (4, 7, 10):
        d.arc([cx - rr, cy - rr, cx + rr, cy + rr], start=200, end=340,
              fill=(255, 214, 110), width=2)
        d.arc([cx - rr, cy - rr, cx + rr, cy + rr], start=20, end=160,
              fill=(255, 214, 110), width=2)
    # large white magnifier ring over the fingerprint
    d.ellipse([x + 84, y + 8, x + 124, y + 40], outline=(255, 255, 255), width=3)
    d.line([(x + 116, y + 34), (x + 136, y + 48)], fill=(255, 255, 255), width=3)
    # small warning triangle, bottom right
    d.polygon([(x + 140, y + 48), (x + 150, y + 48), (x + 145, y + 36)], fill=(255, 200, 40))
    d.text((x + 143, y + 40), "!", font=font(SANS_B, 8), fill=(40, 40, 40))


def scene_race(d, x, y, w, h):
    _small_bg(d, x, y, w, h, (20, 24, 40))
    # checkered start line across the top
    for i in range(15):
        d.rectangle([x + i * 11, y, x + (i + 1) * 11, y + 10],
                    fill=(255, 255, 255) if i % 2 == 0 else (20, 20, 20))
    # grandstand strip with crowd dots
    d.rectangle([x, y + 10, x + w, y + 18], fill=(60, 60, 80))
    for cx in range(6, w - 4, 9):
        d.ellipse([x + cx, y + 12, x + cx + 5, y + 17],
                  fill=(255, 220, 130) if cx % 18 == 6 else (200, 200, 220))
    # two floodlight poles with glow dots
    for px in (10, 138):
        d.line([(x + px, y + 18), (x + px, y + 30)], fill=(180, 180, 180), width=2)
        d.ellipse([x + px - 3, y + 14, x + px + 3, y + 20], fill=(255, 240, 180))
    # red F1 car with speed lines
    d.rectangle([x + 42, y + 30, x + 112, y + 40], fill=(180, 30, 30))
    d.rectangle([x + 62, y + 22, x + 88, y + 30], fill=(180, 30, 30))
    d.polygon([(x + 42, y + 30), (x + 34, y + 34), (x + 42, y + 38)], fill=(120, 20, 20))
    for wx in (52, 96):
        d.ellipse([x + wx, y + 38, x + wx + 12, y + 50], fill=(10, 10, 10),
                  outline=(180, 180, 180), width=1)
    d.line([(x + 14, y + 34), (x + 34, y + 34)], fill=(255, 220, 130), width=2)
    d.line([(x + 20, y + 42), (x + 36, y + 42)], fill=(255, 220, 130), width=2)


def scene_trade(d, x, y, w, h):
    """EU-Indonesia trade pact: EU flag left, Indonesia flag right, a
    signed document with a red seal in the middle."""
    _small_bg(d, x, y, w, h, (233, 227, 204))
    # EU flag: blue field with a ring of yellow stars
    d.rectangle([x + 8, y + 18, x + 48, y + 42], fill=(0, 51, 153))
    for k in range(8):
        ang = math.radians(k * 45)
        sx = x + 28 + int(9 * math.cos(ang))
        sy = y + 30 + int(7 * math.sin(ang))
        d.ellipse([sx - 1, sy - 1, sx + 1, sy + 1], fill=(255, 210, 0))
    # Indonesia flag: red over white
    d.rectangle([x + 108, y + 18, x + 148, y + 30], fill=(220, 30, 30))
    d.rectangle([x + 108, y + 30, x + 148, y + 42], fill=(255, 255, 255),
                outline=(60, 55, 45), width=1)
    # signed document in the middle: white sheet, three lines, red seal
    d.rectangle([x + 56, y + 14, x + 100, y + 46], fill=(255, 255, 255),
                outline=(60, 55, 45), width=1)
    for ly in (20, 26, 32):
        d.line([(x + 61, y + ly), (x + 95, y + ly)], fill=(120, 115, 100), width=1)
    d.ellipse([x + 84, y + 34, x + 96, y + 46], fill=(163, 18, 18))
    d.line([(x + 88, y + 42), (x + 91, y + 45), (x + 95, y + 38)],
           fill=(255, 255, 255), width=2)


def scene_raid(d, x, y, w, h):
    """Night raid in Sinaloa: dark street, building with lit windows,
    searchlight beam, armoured vehicle with flashing lights."""
    _small_bg(d, x, y, w, h, (28, 28, 44))
    for sx, sy in [(0.08, 0.10), (0.30, 0.06), (0.55, 0.12), (0.80, 0.08), (0.92, 0.16)]:
        d.ellipse([x + int(w * sx) - 1, y + int(h * sy) - 1,
                   x + int(w * sx) + 1, y + int(h * sy) + 1], fill=(255, 255, 255))
    # searchlight beam from the top right, clear of the red topic bar
    d.polygon([(x + 148, y + 16), (x + 156, y + 16),
               (x + 96, y + 44), (x + 84, y + 44)], fill=(90, 90, 110))
    d.polygon([(x + 150, y + 16), (x + 154, y + 16),
               (x + 94, y + 44), (x + 88, y + 44)], fill=(200, 200, 170))
    # building with lit windows on the left
    d.rectangle([x + 8, y + 16, x + 44, y + 44], fill=(60, 60, 80))
    for wy in range(2):
        for wx in range(3):
            lit = (wx + wy) % 2 == 0
            d.rectangle([x + 13 + wx * 10, y + 21 + wy * 11,
                         x + 19 + wx * 10, y + 27 + wy * 11],
                        fill=(255, 214, 110) if lit else (18, 18, 28))
    # armoured vehicle with a turret and two flashing dots
    d.rectangle([x + 56, y + 34, x + 128, y + 46], fill=(50, 52, 62))
    d.rectangle([x + 80, y + 26, x + 104, y + 34], fill=(50, 52, 62))
    d.ellipse([x + 64, y + 44, x + 74, y + 52], fill=(10, 10, 10))
    d.ellipse([x + 108, y + 44, x + 118, y + 52], fill=(10, 10, 10))
    d.ellipse([x + 86, y + 22, x + 92, y + 28], fill=(200, 30, 30))
    d.ellipse([x + 96, y + 22, x + 102, y + 28], fill=(40, 90, 220))


def scene_robot(d, x, y, w, h):
    """UN 'killer robot' talks: grey robot with yellow eyes on a light
    background, crossed out by a red circle-slash."""
    _small_bg(d, x, y, w, h, (228, 228, 220))
    # robot body and head
    d.rectangle([x + 58, y + 26, x + 102, y + 50], fill=(140, 145, 155),
                outline=(60, 55, 45), width=1)
    d.rectangle([x + 62, y + 8, x + 98, y + 26], fill=(160, 165, 175),
                outline=(60, 55, 45), width=1)
    d.line([(x + 80, y + 2), (x + 80, y + 8)], fill=(60, 55, 45), width=2)
    d.ellipse([x + 77, y - 1, x + 83, y + 5], fill=(255, 60, 60))
    # yellow eyes
    d.ellipse([x + 68, y + 14, x + 76, y + 22], fill=(255, 214, 110))
    d.ellipse([x + 84, y + 14, x + 92, y + 22], fill=(255, 214, 110))
    # chest panel with two buttons
    d.rectangle([x + 68, y + 32, x + 76, y + 40], fill=(60, 55, 45))
    d.rectangle([x + 84, y + 32, x + 92, y + 40], fill=(200, 30, 30))
    # arms
    d.rectangle([x + 46, y + 30, x + 58, y + 46], fill=(140, 145, 155))
    d.rectangle([x + 102, y + 30, x + 114, y + 46], fill=(140, 145, 155))
    # red circle-slash over the robot
    d.ellipse([x + 52, y + 2, x + 112, y + 52], outline=(200, 30, 30), width=3)
    d.line([(x + 54, y + 50), (x + 110, y + 4)], fill=(200, 30, 30), width=3)


def scene_space(d, x, y, w, h):
    """BepiColombo at Mercury: dark sky, cratered grey planet, small
    probe with blue solar panels on an orbit arc."""
    _small_bg(d, x, y, w, h, (10, 14, 30))
    for sx, sy in [(0.08, 0.10), (0.22, 0.06), (0.40, 0.12), (0.58, 0.06),
                   (0.75, 0.10), (0.88, 0.06), (0.95, 0.22), (0.30, 0.20)]:
        d.ellipse([x + int(w * sx) - 1, y + int(h * sy) - 1,
                   x + int(w * sx) + 1, y + int(h * sy) + 1], fill=(255, 255, 255))
    # orbit arc across the scene
    d.arc([x + 10, y - 6, x + w - 10, y + 44], start=180, end=360,
          fill=(120, 130, 160), width=1)
    # Mercury: grey disc with craters, bottom left
    d.ellipse([x + 12, y + 18, x + 52, y + 54], fill=(160, 155, 145))
    for cx, cy, cr in [(24, 30, 4), (36, 42, 5), (30, 48, 3), (42, 28, 3)]:
        d.ellipse([x + cx - cr, y + cy - cr, x + cx + cr, y + cy + cr],
                  fill=(120, 115, 105))
    # probe: white body with two blue solar panels, top right
    d.rectangle([x + 108, y + 16, x + 122, y + 28], fill=(230, 230, 220),
                outline=(60, 55, 45), width=1)
    d.rectangle([x + 88, y + 18, x + 108, y + 26], fill=(40, 90, 180))
    d.rectangle([x + 122, y + 18, x + 142, y + 26], fill=(40, 90, 180))
    d.line([(x + 115, y + 28), (x + 115, y + 34)], fill=(200, 200, 200), width=2)
    # small gold dish on the probe
    d.ellipse([x + 112, y + 10, x + 118, y + 16], fill=(255, 200, 60))


def scene_quake(d, x, y, w, h):
    """Banda Sea quake: pale sky, leaning building with a crack, a red
    seismograph zigzag, cracked ground."""
    _small_bg(d, x, y, w, h, (200, 220, 235))
    # ground strip
    d.rectangle([x, y + 40, x + w, y + h], fill=(190, 180, 150))
    # leaning building: a parallelogram with windows, clear of the bar
    d.polygon([(x + 20, y + 18), (x + 48, y + 18), (x + 56, y + 40), (x + 28, y + 40)],
              fill=(120, 115, 100))
    for wy in range(2):
        for wx in range(3):
            d.rectangle([x + 26 + wx * 9, y + 23 + wy * 9,
                         x + 31 + wx * 9, y + 28 + wy * 9], fill=(255, 214, 110))
    # crack down the building face
    d.line([(x + 38, y + 18), (x + 42, y + 26), (x + 38, y + 33), (x + 44, y + 40)],
           fill=(40, 40, 40), width=2)
    # red seismograph zigzag across the middle
    d.line([(x + 60, y + 30), (x + 72, y + 30), (x + 76, y + 22), (x + 80, y + 38),
            (x + 84, y + 26), (x + 88, y + 34), (x + 92, y + 30), (x + 110, y + 30)],
           fill=(200, 30, 30), width=2)
    # cracked ground: dark zigzag along the bottom
    d.line([(x + 8, y + 46), (x + 30, y + 50), (x + 52, y + 45), (x + 78, y + 51),
            (x + 104, y + 46), (x + 130, y + 50), (x + 152, y + 47)],
           fill=(60, 55, 45), width=2)
    # a small tilted house on the right
    d.polygon([(x + 118, y + 30), (x + 142, y + 30), (x + 146, y + 40), (x + 122, y + 40)],
              fill=(150, 110, 80))
    d.polygon([(x + 116, y + 30), (x + 130, y + 22), (x + 146, y + 30)],
              fill=(120, 60, 50))


def scene_march(d, x, y, w, h):
    """Cost-of-living marches: crowd of head dots under three placards
    on sticks, one with a red stripe."""
    _small_bg(d, x, y, w, h, (233, 227, 204))
    # three placards held above the crowd
    for px, stripe in [(18, True), (66, False), (114, True)]:
        d.line([(x + px + 10, y + 22), (x + px + 10, y + 34)], fill=(90, 84, 70), width=2)
        d.rectangle([x + px, y + 8, x + px + 24, y + 22], fill=(255, 255, 255),
                    outline=(60, 55, 45), width=1)
        if stripe:
            d.rectangle([x + px + 2, y + 13, x + px + 22, y + 17], fill=(163, 18, 18))
        else:
            d.line([(x + px + 3, y + 13), (x + px + 21, y + 13)], fill=(60, 55, 45), width=1)
            d.line([(x + px + 3, y + 17), (x + px + 21, y + 17)], fill=(60, 55, 45), width=1)
    # crowd: two rows of heads and shoulders
    for i, cx in enumerate(range(6, w - 6, 12)):
        d.ellipse([x + cx, y + 36, x + cx + 7, y + 43],
                  fill=(60, 55, 45) if i % 3 else (120, 60, 40))
        d.ellipse([x + cx - 2, y + 44, x + cx + 9, y + 50],
                  fill=(60, 55, 45) if i % 3 else (120, 60, 40))
    for i, cx in enumerate(range(12, w - 12, 14)):
        d.ellipse([x + cx, y + 28, x + cx + 6, y + 34],
                  fill=(90, 84, 70) if i % 2 else (40, 40, 40))


def scene_flood(d, x, y, w, h):
    """Florida flood: grey rain sky, two houses half-submerged, water
    with wave arcs up to the roofline."""
    _small_bg(d, x, y, w, h, (200, 220, 235))
    # rain streaks
    for rx, ry in [(16, 6), (40, 10), (66, 6), (92, 10), (118, 6), (142, 10)]:
        d.line([(x + rx, y + ry), (x + rx - 2, y + ry + 6)], fill=(150, 165, 185), width=1)
    # two houses with pitched roofs
    d.rectangle([x + 12, y + 26, x + 52, y + 40], fill=(200, 170, 120))
    d.polygon([(x + 10, y + 26), (x + 32, y + 14), (x + 54, y + 26)], fill=(140, 60, 50))
    d.rectangle([x + 96, y + 22, x + 140, y + 40], fill=(180, 150, 110))
    d.polygon([(x + 94, y + 22), (x + 118, y + 10), (x + 142, y + 22)], fill=(120, 60, 50))
    # water covering the lower half, with wave arcs
    d.rectangle([x, y + 38, x + w, y + h], fill=(40, 100, 150))
    d.arc([x + 6, y + 40, x + 46, y + 52], start=180, end=360, fill=(255, 255, 255), width=2)
    d.arc([x + 60, y + 42, x + 104, y + 54], start=180, end=360, fill=(255, 255, 255), width=2)
    d.arc([x + 112, y + 40, x + 150, y + 52], start=180, end=360, fill=(255, 255, 255), width=2)
    # a roof peak and a chimney poking out of the water
    d.polygon([(x + 64, y + 38), (x + 74, y + 30), (x + 84, y + 38)], fill=(140, 60, 50))


SCENES_BIG = {"cop31": scene_cop31, "bahrain": scene_bahrain, "sparta": scene_sparta}
SCENES_SMALL = {"trade": scene_trade, "raid": scene_raid, "robot": scene_robot,
                "space": scene_space, "boat": scene_boat, "quake": scene_quake,
                "hospital": scene_hospital, "basket": scene_basket, "flood": scene_flood,
                "march": scene_march, "fbi": scene_fbi, "race": scene_race}


def render(data, out_path):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    m = 26
    d.rectangle([10, 10, W - 11, H - 11], outline=RULE, width=2)
    d.rectangle([15, 15, W - 16, H - 16], outline=RULE, width=1)
    warnings = []

    # --- kicker + meta -------------------------------------------------
    y = 24
    f_kick = font(SANS_B, 11)
    d.text((m, y), "THE WORLD IN ONE DAY", font=f_kick, fill=RED)
    f_meta = font(SANS, 10)
    meta = data["meta"]
    d.text((W - m - d.textlength(meta, font=f_meta), y), meta, font=f_meta, fill=MUTED)

    # --- masthead: the date --------------------------------------------
    f_mast = font(SERIF_B, 64)
    title = data["date_label"]
    while d.textlength(title, font=f_mast) > W - 2 * m and f_mast.size > 40:
        f_mast = font(SERIF_B, f_mast.size - 2)
    d.text(((W - d.textlength(title, font=f_mast)) / 2, 40), title, font=f_mast, fill=INK)
    f_red = font(SERIF_I, 13, fallback=SERIF)
    red_line = data["red_line"]
    while d.textlength(red_line, font=f_red) > W - 2 * m - 10 and f_red.size > 10:
        f_red = font(SERIF_I, f_red.size - 1, fallback=SERIF)
    d.text(((W - d.textlength(red_line, font=f_red)) / 2, 108), red_line,
           font=f_red, fill=RED)
    d.line([(m, 130), (W - m, 130)], fill=RULE, width=2)

    # --- numbers strip --------------------------------------------------
    y = 136
    nums = data["numbers"]
    cell_w = (W - 2 * m) // len(nums)
    f_num = font(SERIF_B, 20)
    f_lab = font(SANS, 8.5)
    for i, (num, lab) in enumerate(nums):
        cx = m + i * cell_w + cell_w // 2
        if i:
            d.line([(m + i * cell_w, y + 4), (m + i * cell_w, y + 40)], fill=LIGHT, width=1)
        d.text((cx - d.textlength(num, font=f_num) / 2, y), num, font=f_num, fill=RED)
        lab_lines = wrap(d, lab, f_lab, cell_w - 10)
        ly = y + 26
        for ln in lab_lines[:2]:
            d.text((cx - d.textlength(ln, font=f_lab) / 2, ly), ln, font=f_lab, fill=MUTED)
            ly += 10

    # --- region colour bar ----------------------------------------------
    y = 184
    bar = data["regions_bar"]
    total = sum(c for _, c, _ in bar)
    bx = m
    f_bar = font(SANS_B, 10)
    for name, cnt, color in bar:
        seg_w = int((W - 2 * m) * cnt / total)
        d.rectangle([bx, y, bx + seg_w, y + 20], fill=color)
        label = f"{name} {cnt}"
        tw = d.textlength(label, font=f_bar)
        if tw > seg_w - 8:
            f_bar = font(SANS_B, 8)
            tw = d.textlength(label, font=f_bar)
        d.text((bx + (seg_w - tw) / 2, y + 4), label, font=f_bar, fill=(255, 255, 255))
        bx += seg_w
        f_bar = font(SANS_B, 10)

    # --- dark UTC strip ---------------------------------------------------
    y = 208
    d.rectangle([m, y, W - m, y + 20], fill=NAVY)
    f_utc_l = font(SANS_B, 10)
    f_utc = font(SANS, 10)
    label = "THE DAY IN UTC"
    parts = [(label, f_utc_l, SALMON)]
    for t, ev in data["utc"]:
        parts.append(("  ·  " + t + " ", f_utc_l, SALMON))
        parts.append((ev, f_utc, (255, 255, 255)))
    total_w = sum(d.textlength(t, font=f) for t, f, _ in parts)
    while total_w > W - 2 * m - 8 and f_utc.size > 8:
        f_utc = font(SANS, f_utc.size - 1)
        f_utc_l = font(SANS_B, f_utc_l.size - 1)
        total_w = sum(d.textlength(t, font=f) for t, f, _ in parts)
    tx = m + (W - 2 * m - total_w) / 2
    for t, f, col in parts:
        d.text((tx, y + 4), t, font=f, fill=col)
        tx += d.textlength(t, font=f)

    # --- 3 big illustrated stories ---------------------------------------
    y = 234
    big_w = (W - 2 * m - 2 * 12) // 3
    f_tag = font(SANS_B, 10.5)
    f_bhead = font(SERIF_B, 19)
    f_bsum = font(SANS, 11)
    f_bsrc = font(SANS, 9.5)
    for i, st in enumerate(data["big"]):
        x0 = m + i * (big_w + 12)
        SCENES_BIG[st["scene"]](d, x0, y, big_w, 100)
        # red topic bar top-left + white secondary bar top-right
        wb = whitebar(d, x0 + big_w, y, 10, st["label2"], h=16) if st.get("label2") else 0
        redbar(d, x0, y, 11, st["label"], h=16, max_w=big_w - wb - 8)
        ty = y + 104
        tag = f"{st['num']}  {st['place']} · {st['topic']}"
        d.text((x0, ty), tag, font=f_tag, fill=INK)
        chip(d, x0 + big_w, ty - 1, st["badge"], size=9)
        hy = ty + 18
        hl = wrap(d, st["headline"], f_bhead, big_w)
        if len(hl) > 3:
            warnings.append(f"big {st['num']} headline {len(hl)} lines")
        hy = draw_wrapped(d, x0, hy, hl[:3], f_bhead, INK, 23)
        sm = wrap(d, st["summary"], f_bsum, big_w)
        if len(sm) > 3:
            warnings.append(f"big {st['num']} summary {len(sm)} lines")
        hy = draw_wrapped(d, x0, hy + 1, sm[:3], f_bsum, MUTED, 14.5)
        d.text((x0, hy + 1), f"({st['source']})", font=f_bsrc, fill=MUTED)

    # --- 12 small illustrated stories, 2 rows x 6 ------------------------
    y = 487
    sm_w = (W - 2 * m - 5 * 10) // 6
    f_stag = font(SANS_B, 8.5)
    f_shead = font(SERIF_B, 12.5)
    f_ssum = font(SANS, 9.5)
    for row in range(2):
        for col in range(6):
            st = data["small"][row * 6 + col]
            x0 = m + col * (sm_w + 10)
            sy = y + row * 125
            SCENES_SMALL[st["scene"]](d, x0, sy, sm_w, 54)
            # red topic bar top-left of the illustration
            redbar(d, x0, sy, 8, st["label"], h=13, max_w=sm_w)
            chip(d, x0 + sm_w - 3, sy + 54 - 15, st["badge"], size=7)
            ty = sy + 58
            tag = f"{st['num']} {st['place']} · {st['topic']}"
            tag_lines = wrap(d, tag, f_stag, sm_w)
            ty = draw_wrapped(d, x0, ty, tag_lines[:1], f_stag, INK, 11)
            hy = ty + 2
            hl = wrap(d, st["headline"], f_shead, sm_w)
            if len(hl) > 2:
                warnings.append(f"small {st['num']} headline {len(hl)} lines")
            hy = draw_wrapped(d, x0, hy, hl[:2], f_shead, INK, 15)
            sm = wrap(d, f"{st['summary']} ({st['source']})", f_ssum, sm_w)
            if len(sm) > 2:
                warnings.append(f"small {st['num']} summary {len(sm)} lines")
            draw_wrapped(d, x0, hy + 1, sm[:2], f_ssum, MUTED, 12)

    # --- bottom: map + ALSO ON -------------------------------------------
    y = 749
    f_sect = font(SANS_B, 12)
    d.text((m, y), "WHERE IT HAPPENED", font=f_sect, fill=RED)
    f_cap = font(SANS, 9)
    d.text((m + 300 - d.textlength("pins match story numbers", font=f_cap), y + 2),
           "pins match story numbers", font=f_cap, fill=MUTED)
    map_x, map_y, map_w, map_h = m, y + 16, 300, 84
    d.rectangle([map_x, map_y, map_x + map_w, map_y + map_h],
                fill=(238, 238, 226), outline=MAP_LINE, width=1)

    def proj(lon, lat):
        return (map_x + (lon + 180) / 360.0 * map_w,
                map_y + (90 - lat) / 150.0 * map_h)

    for poly in CONTINENTS:
        d.polygon([proj(lon, lat) for lon, lat in poly], fill=MAP_LAND, outline=MAP_LINE)
    f_pin = font(SANS_B, 7)
    for num, lon, lat in data["pins"]:
        px, py = proj(lon, lat)
        px = min(max(px, map_x + 7), map_x + map_w - 7)
        py = min(max(py, map_y + 7), map_y + map_h - 7)
        d.ellipse([px - 6, py - 6, px + 6, py + 6], fill=RED, outline=(255, 255, 255), width=1)
        lbl = str(num)
        d.text((px - d.textlength(lbl, font=f_pin) / 2, py - 5), lbl,
               font=f_pin, fill=(255, 255, 255))

    ax = m + 300 + 16
    aw = W - m - ax
    d.text((ax, y), "ALSO ON SATURDAY 21 NOVEMBER — 22 MORE STORIES", font=f_sect, fill=RED)
    f_also = font(SANS, 9)
    col_w = (aw - 10) // 2
    items = data["also"]
    for idx, it in enumerate(items):
        col = idx // 11
        row = idx % 11
        ix = ax + col * (col_w + 10)
        iy = y + 18 + row * 11
        line = f"{it['num']} {it['region']}: {it['text']} ({it['source']})"
        if d.textlength(line, font=f_also) > col_w:
            warnings.append(f"also {it['num']} line too long: {len(line)} chars")
        d.text((ix, iy), line, font=f_also, fill=INK)

    # --- DATE CHECK box ----------------------------------------------------
    dy = 890
    dc = data["date_check"]
    f_dc_t = font(SANS_B, 11)
    f_dc = font(SANS, 10)
    dc_lines = wrap(d, dc, f_dc, W - 2 * m - 130)
    dc_h = 12 + len(dc_lines) * 13 + 8
    d.rectangle([m, dy, W - m, dy + dc_h], outline=RED, width=1)
    d.text((m + 8, dy + 6), "DATE CHECK", font=f_dc_t, fill=RED)
    draw_wrapped(d, m + 118, dy + 6, dc_lines, f_dc, INK, 13)

    # --- footer -------------------------------------------------------------
    fy = 942
    d.line([(m, fy), (W - m, fy)], fill=RULE, width=1)
    f_foot = font(SANS, 9.5)
    legend = data["legend"]
    d.text(((W - d.textlength(legend, font=f_foot)) / 2, fy + 4), legend,
           font=f_foot, fill=MUTED)
    foot = data["footer"]
    d.text(((W - d.textlength(foot, font=f_foot)) / 2, fy + 16), foot,
           font=f_foot, fill=MUTED)

    # --- bottom navy bar -----------------------------------------------------
    d.rectangle([15, 984, W - 16, 1004], fill=NAVY)
    f_bar = font(SANS_B, 9)
    d.text((m, 990), "THE WORLD IN ONE DAY", font=f_bar, fill=(255, 255, 255))
    tail = "SATURDAY 21 NOVEMBER 2026  ·  ONE PAGE"
    d.text((W - m - d.textlength(tail, font=f_bar), 990), tail, font=f_bar,
           fill=(255, 255, 255))

    img.save(out_path, "PNG", optimize=True)
    for wmsg in sorted(set(warnings)):
        print("TRUNCATED:", wmsg)
    print("warnings:", len(warnings))
    return out_path


if __name__ == "__main__":
    data = json.load(open(sys.argv[1]))
    out = sys.argv[2]
    render(data, out)
    print("wrote", out, os.path.getsize(out), "bytes")
