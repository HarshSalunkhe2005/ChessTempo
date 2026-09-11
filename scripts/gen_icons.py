"""One-off script to generate the PWA app icons referenced by
frontend/public/manifest.json but never actually committed
(docs/PLAN.md Phase 5). Not part of the app itself — a dev-time tool, run
once and the output committed.

Draws the same knight glyph + gold-on-charcoal palette used by the brand
mark elsewhere in the app (see frontend/app/globals.css --accent / --bg),
rather than a generic placeholder.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BG = (17, 19, 24, 255)  # #111318 — manifest.json background_color/theme_color
ACCENT = (217, 164, 65, 255)  # #d9a441 — globals.css --accent
FONT_PATH = r"C:\Windows\Fonts\seguisym.ttf"
KNIGHT_GLYPH = "\u265e"  # ♞

OUT_DIR = Path(__file__).resolve().parents[1] / "frontend" / "public"


def render(size: int, corner_radius_frac: float = 0.22) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    radius = int(size * corner_radius_frac)
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=BG)

    font_size = int(size * 0.66)
    font = ImageFont.truetype(FONT_PATH, font_size)

    bbox = draw.textbbox((0, 0), KNIGHT_GLYPH, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pos = ((size - text_w) / 2 - bbox[0], (size - text_h) / 2 - bbox[1])
    draw.text(pos, KNIGHT_GLYPH, font=font, fill=ACCENT)
    return img


def main() -> None:
    for size in (192, 512):
        img = render(size)
        out_path = OUT_DIR / f"icon-{size}.png"
        img.save(out_path)
        print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
