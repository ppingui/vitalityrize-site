#!/usr/bin/env python3
"""Generate web assets from the app's own art. Run once, or after a screenshot
refresh: python3 make_assets.py

Sources (the app repo, assumed to sit beside this one):
    ../VitalityRise/marketing/screenshots/out/raw/en/*.png   1290x2796 clean screens
    ../VitalityRise/AppIcon.png                              1024x1024, no alpha

Requires Pillow. Everything else in this repo is stdlib-only.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
APP = HERE.parent / "VitalityRise"
RAW_SRC = APP / "marketing" / "screenshots" / "out" / "raw" / "en"
ICON_SRC = APP / "AppIcon.png"
OUT = HERE / "assets"
SHOT_OUT = OUT / "shots"

ROUNDED = "/System/Library/Fonts/SFNSRounded.ttf"

# Matches styles.css.
INK = (0, 0, 0)
VIOLET = (122, 71, 235)
BLUE = (56, 122, 250)
MINT = (87, 199, 194)
TEXT = (255, 255, 255)
MUTED = (166, 168, 179)

SHOTS = ("today", "session", "progress", "results", "privacy")


def rounded(size: int, weight: str = "Bold") -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(ROUNDED, size)
    try:
        f.set_variation_by_name(weight)
    except Exception:
        pass
    return f


def screenshots() -> None:
    """Clean app screens, not the App Store marketing panels — those have baked-in
    headlines that would fight the page copy."""
    SHOT_OUT.mkdir(parents=True, exist_ok=True)
    for name in SHOTS:
        src = RAW_SRC / f"{name}.png"
        if not src.exists():
            print(f"  missing {src}")
            continue
        im = Image.open(src).convert("RGB")
        # 2x the 12rem CSS display width — retina-sharp, small on the wire.
        im = im.resize((430, 932), Image.LANCZOS)
        dst = SHOT_OUT / f"{name}.jpg"
        im.save(dst, "JPEG", quality=82, optimize=True, progressive=True)
        print(f"  {dst.relative_to(HERE)}  {dst.stat().st_size // 1024} KB")


def icons() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    icon = Image.open(ICON_SRC).convert("RGBA")
    for size, name in ((180, "icon-180.png"), (32, "favicon.png")):
        icon.resize((size, size), Image.LANCZOS).save(OUT / name, "PNG", optimize=True)
        print(f"  assets/{name}")


def glow(w: int, h: int) -> Image.Image:
    """Radial brand glows on black, matching the site's CSS ground."""
    base = Image.new("RGB", (w, h), INK)
    for cx, cy, rad, color, strength in (
        (0.10, -0.12, 0.90, VIOLET, 0.34),
        (0.94, 0.02, 0.78, BLUE, 0.28),
        (0.50, 1.10, 0.70, MINT, 0.12),
    ):
        layer = Image.new("RGB", (w, h), color)
        mask = Image.new("L", (w, h), 0)
        d = ImageDraw.Draw(mask)
        px, py, r = cx * w, cy * h, rad * w
        steps = 90
        for i in range(steps, 0, -1):
            t = i / steps
            a = int(255 * strength * (1 - t) ** 2.0)
            d.ellipse([px - r * t, py - r * t * 0.72, px + r * t, py + r * t * 0.72],
                      fill=a)
        base = Image.composite(layer, base, mask)
    return base


def og() -> None:
    W, H = 1200, 630
    im = glow(W, H)
    d = ImageDraw.Draw(im)

    d.text((72, 148), "Pelvic floor training", font=rounded(76, "Heavy"), fill=TEXT)
    d.text((72, 236), "for men.", font=rounded(76, "Heavy"), fill=BLUE)
    d.text((72, 366),
           "Guided sessions and a 30-day plan on iPhone.\n"
           "No account. Your answers stay on the device.",
           font=rounded(31, "Medium"), fill=MUTED, spacing=12)
    d.text((72, 520), "vitalityrize.me", font=rounded(30, "Semibold"), fill=MINT)

    icon = Image.open(ICON_SRC).convert("RGBA").resize((132, 132), Image.LANCZOS)
    mask = Image.new("L", (132, 132), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, 131, 131], radius=30, fill=255)
    im.paste(icon, (W - 132 - 72, 72), mask)

    im.save(OUT / "og.png", "PNG", optimize=True)
    print(f"  assets/og.png  {(OUT / 'og.png').stat().st_size // 1024} KB")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    icons()
    screenshots()
    og()
