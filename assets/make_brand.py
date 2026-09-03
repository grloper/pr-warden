#!/usr/bin/env python3
"""Generate PR-Warden brand assets (logo + Open Graph image) with Pillow only.

Outputs (PNG):
  assets/logo.png   512x512  transparent shield mark
  assets/og.png    1200x630  social preview card

Re-run:  py assets/make_brand.py
"""
from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))

# Palette ---------------------------------------------------------------
BG_TOP = (13, 20, 38)      # deep navy
BG_BOT = (8, 12, 24)
EMERALD = (52, 211, 153)   # check / accent
SHIELD_DARK = (23, 34, 58)
SHIELD_LIGHT = (38, 56, 92)
WHITE = (235, 240, 248)
MUTED = (148, 163, 184)    # slate-400

FONT_DIR = r"C:\Windows\Fonts"


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    path = os.path.join(FONT_DIR, name)
    if os.path.exists(path):
        return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def vertical_gradient(size: tuple[int, int], top, bottom) -> Image.Image:
    w, h = size
    base = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / max(h - 1, 1)
        base.putpixel(
            (0, y),
            tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)),
        )
    return base.resize((w, h))


def shield_points(cx: float, top: float, bottom: float, half_w: float):
    """Classic shield outline, centered on cx, spanning top..bottom."""
    w2 = half_w
    return [
        (cx - w2, top + w2 * 0.35),
        (cx - w2, top),
        (cx, top + w2 * 0.28),
        (cx + w2, top),
        (cx + w2, top + w2 * 0.35),
        (cx, bottom),
    ]


def draw_check(d, cx, top, bottom, half_w, width, color):
    x0 = cx - half_w * 0.36
    d.line([(x0, top + (bottom - top) * 0.54),
            (cx - half_w * 0.03, top + (bottom - top) * 0.74),
            (cx + half_w * 0.42, top + (bottom - top) * 0.26)],
           fill=color, width=width, joint="curve")


def make_logo() -> Image.Image:
    S = 512
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    cx, top, bottom, hw = S / 2, 64, S - 64, 190

    # soft drop shadow
    sh = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    sd.polygon(shield_points(cx, top + 16, bottom + 16, hw), fill=(0, 0, 0, 80))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(18)))

    # layered shield fill: vertical sheen
    sheen = vertical_gradient((S, S), SHIELD_LIGHT, SHIELD_DARK).convert("RGBA")
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).polygon(shield_points(cx, top, bottom, hw), fill=255)
    img.paste(sheen, (0, 0), mask)

    # rim + check
    d = ImageDraw.Draw(img)
    d.polygon(shield_points(cx, top, bottom, hw), outline=(129, 186, 238, 120),
              width=5)
    draw_check(d, cx, top, bottom, hw, 27, EMERALD)
    return img


def make_og() -> Image.Image:
    W, H = 1200, 630
    img = vertical_gradient((W, H), BG_TOP, BG_BOT).convert("RGBA")
    d = ImageDraw.Draw(img)

    # faint diagonal grid + glow
    for i, x in enumerate(range(-200, W + 200, 92)):
        d.line([(x, 0), (x + 280, H)], fill=(255, 255, 255, 7), width=1)
    d.ellipse((W - 460, -300, W + 300, 460), fill=(96, 165, 250, 22))

    # logo mark, left
    mark = make_logo().resize((340, 340), Image.LANCZOS)
    img.alpha_composite(mark, (72, 145))

    x = 480
    title_f = font("segoeuib.ttf", 100)
    sub_f = font("segoeui.ttf", 40)
    small_f = font("segoeui.ttf", 31)

    d.text((x, 138), "PR-Warden", font=title_f, fill=WHITE)
    d.rounded_rectangle((x + 8, 262, x + 590, 273), radius=5, fill=EMERALD)
    d.text((x, 322), "Your private, always-on AI code reviewer.", font=sub_f,
           fill=(203, 213, 225))
    d.text((x, 386), "Self-hosted  \u00b7  model-agnostic  \u00b7  zero per-review cost",
           font=small_f, fill=MUTED)

    chips = ["MIT", "Ollama-ready", "GitHub App"]
    chip_x, chip_h = x, 64
    for label in chips:
        w = d.textlength(label, font=small_f) + 58
        d.rounded_rectangle((chip_x, 500, chip_x + w, 500 + chip_h),
                            radius=chip_h // 2, fill=(30, 41, 66, 230),
                            outline=(71, 85, 105, 255), width=2)
        d.text((chip_x + 29, 512), label, font=small_f, fill=WHITE)
        chip_x += w + 28

    d.text((W - 40, H - 60), "github.com/grloper/pr-warden", font=small_f,
           fill=(100, 116, 139), anchor="rs")
    return img


if __name__ == "__main__":
    make_logo().save(os.path.join(HERE, "logo.png"))
    make_og().save(os.path.join(HERE, "og.png"))
    print("wrote", os.path.join(HERE, "logo.png"),
          os.path.join(HERE, "og.png"))
