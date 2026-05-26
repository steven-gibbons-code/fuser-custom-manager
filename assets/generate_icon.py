"""Generate assets/icon.ico — run once: python assets/generate_icon.py"""
from pathlib import Path
from PIL import Image, ImageDraw

SIZES = [16, 32, 48]
OUT = Path(__file__).parent / "icon.ico"

BG_DARK   = (28, 28, 28, 255)
BLUE      = (37, 99, 235, 255)
WHITE     = (220, 220, 220, 255)


def _draw_frame(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    radius = max(2, size // 6)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=BG_DARK)

    # Music note: filled oval (note head) + stem + flag
    s = size / 48.0  # scale factor relative to 48px base

    # Note head
    hx, hy = int(10 * s), int(28 * s)
    hw, hh = max(2, int(12 * s)), max(2, int(10 * s))
    d.ellipse([hx, hy, hx + hw, hy + hh], fill=BLUE)

    # Stem
    sx = hx + hw - max(1, int(2 * s))
    d.rectangle([sx, int(12 * s), sx + max(1, int(3 * s)), hy + hh // 2], fill=BLUE)

    # Flag (two small arcs approximated as lines)
    fx = sx + max(1, int(3 * s))
    for i in range(2):
        y_start = int((12 + i * 6) * s)
        y_end = int((18 + i * 6) * s)
        d.line([fx, y_start, fx + int(8 * s), y_start + int(4 * s),
                fx + int(6 * s), y_end], fill=BLUE, width=max(1, int(2 * s)))

    return img


def main():
    # Draw the largest frame; Pillow will rescale it to the other sizes
    base = _draw_frame(48)
    base.save(OUT, format="ICO", sizes=[(16, 16), (32, 32), (48, 48)])
    print(f"Written: {OUT}  ({', '.join(str(s)+'px' for s in SIZES)})")


if __name__ == "__main__":
    main()
