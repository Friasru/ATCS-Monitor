#!/usr/bin/env python3
"""Generate the application icon: app/resources/atcs_monitor.ico (+ .png).

A camera lens crossed by a counting line, on a rounded navy square. Drawn at
1024 px and downsampled, so it stays legible at 16 px.

  .venv/bin/python scripts/make_icon.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

OUT = Path(__file__).resolve().parent.parent / "app" / "resources"
S = 1024
NAVY_TOP, NAVY_BOTTOM = (22, 58, 96), (11, 30, 54)
LINE = (255, 64, 160)  # the magenta of the on-screen counting line
WHITE = (240, 246, 252)
LENS = (64, 156, 255)


def draw() -> Image.Image:
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    # Background: rounded square with a vertical gradient.
    grad = Image.new("RGBA", (S, S))
    gd = ImageDraw.Draw(grad)
    for y in range(S):
        t = y / (S - 1)
        gd.line([(0, y), (S, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(NAVY_TOP, NAVY_BOTTOM)) + (255,))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([24, 24, S - 24, S - 24], radius=210, fill=255)
    img.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(img)
    c, r = S // 2, 300
    # Lens: outer ring, iris, pupil and a highlight.
    d.ellipse([c - r, c - r, c + r, c + r], outline=WHITE, width=70)
    d.ellipse([c - 170, c - 170, c + 170, c + 170], fill=LENS)
    d.ellipse([c - 82, c - 82, c + 82, c + 82], fill=NAVY_BOTTOM)
    d.ellipse([c - 120, c - 140, c - 50, c - 70], fill=(255, 255, 255, 230))
    # Counting line across the lens, with a soft glow.
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(glow).line([(110, 700), (914, 324)], fill=LINE + (170,), width=110)
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(24)))
    d.line([(110, 700), (914, 324)], fill=LINE, width=62)
    for x, y in ((110, 700), (914, 324)):  # the line's end handles, as in the app
        d.ellipse([x - 52, y - 52, x + 52, y + 52], fill=WHITE, outline=LINE, width=20)
    return img


def main() -> Image.Image:
    OUT.mkdir(parents=True, exist_ok=True)
    big = draw()
    sizes = [16, 20, 24, 32, 40, 48, 64, 128, 256]
    big.resize((256, 256), Image.Resampling.LANCZOS).save(OUT / "atcs_monitor.ico", sizes=[(s, s) for s in sizes])
    big.resize((256, 256), Image.Resampling.LANCZOS).save(OUT / "atcs_monitor.png")
    preview = Image.new("RGBA", (sum(sizes) + 10 * len(sizes), 256), (255, 255, 255, 255))
    x = 0
    for s in sizes:
        preview.alpha_composite(big.resize((s, s), Image.Resampling.LANCZOS), (x, 256 - s))
        x += s + 10
    print(f"wrote {OUT / 'atcs_monitor.ico'} ({', '.join(map(str, sizes))} px) and atcs_monitor.png")
    return preview


if __name__ == "__main__":
    import sys

    strip = main()
    if len(sys.argv) > 1:  # optional: write a size preview strip for inspection
        strip.save(sys.argv[1])
