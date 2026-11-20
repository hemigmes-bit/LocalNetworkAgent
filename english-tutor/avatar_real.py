"""avatar_real.py - Genera frames de avatar realista a partir de una foto.
Crea: idle, listening y speaking0-4 con variaciones sutiles (zoom/brillo/bob)
para dar sensacion de vida sin lip-sync.
"""
import os
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AVATAR_DIR = os.path.join(BASE_DIR, "data", "avatar")
SOURCE = os.path.join(AVATAR_DIR, "opt2.jpg")
OUT_SIZE = 360


def _circle_mask(size, feather=2):
    big = size * 4
    mask = Image.new("L", (big, big), 0)
    d = ImageDraw.Draw(mask)
    d.ellipse([feather * 4, feather * 4, big - feather * 4, big - feather * 4], fill=255)
    return mask.resize((size, size), Image.LANCZOS)


def _rounded_photo(src, zoom=1.0, dy=0, brightness=1.0, size=OUT_SIZE):
    im = Image.open(src).convert("RGB")
    w, h = im.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    im = im.crop((left, top, left + side, top + side))
    zs = int(side / zoom)
    off = (side - zs) // 2
    im = im.crop((off, off, off + zs, off + zs)).resize((size, size), Image.LANCZOS)

    # Fondo: la misma foto ampliada y desenfocada (evita cortes feos del circulo)
    bg = ImageEnhance.Brightness(im.filter(ImageFilter.GaussianBlur(22))).enhance(1.06)
    canvas = Image.new("RGB", (size, size), (245, 247, 251))
    canvas.paste(bg, (0, 0))

    # Primer plano: foto al 88% centrada para que la cara quepa entera
    fg_size = int(size * 0.88)
    fg = im.resize((fg_size, fg_size), Image.LANCZOS)
    if brightness != 1.0:
        fg = ImageEnhance.Brightness(fg).enhance(brightness)
    fx = (size - fg_size) // 2
    fy = (size - fg_size) // 2 + dy
    fg_mask = Image.new("L", (fg_size, fg_size), 0)
    ImageDraw.Draw(fg_mask).ellipse([0, 0, fg_size - 1, fg_size - 1], fill=255)
    canvas.paste(fg, (fx, fy), fg_mask)

    rgba = canvas.convert("RGBA")
    rgba.putalpha(_circle_mask(size, feather=3))
    return rgba


def _with_ring(base, color=(91, 141, 239), width=7, glow=True):
    size = base.size[0]
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    pad = 10
    if glow:
        glow_layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow_layer)
        gd.ellipse([pad - 8, pad - 8, size - pad + 8, size - pad + 8],
                   outline=color + (110,), width=18)
        glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(10))
        layer = Image.alpha_composite(layer, glow_layer)
        d = ImageDraw.Draw(layer)
    d.ellipse([pad, pad, size - pad, size - pad], outline=color + (255,), width=width)
    return Image.alpha_composite(base, layer)


def generate():
    if not os.path.exists(SOURCE):
        raise SystemExit("Falta la foto base: " + SOURCE)
    os.makedirs(AVATAR_DIR, exist_ok=True)

    idle = _rounded_photo(SOURCE, zoom=1.0, brightness=1.0)
    idle.save(os.path.join(AVATAR_DIR, "idle.png"))

    listening = _rounded_photo(SOURCE, zoom=1.01, brightness=1.04)
    listening = _with_ring(listening, color=(91, 141, 239), width=7)
    listening.save(os.path.join(AVATAR_DIR, "listening.png"))

    variants = [
        (1.000, 0, 1.00),
        (1.010, -1, 1.03),
        (1.018, 0, 1.01),
        (1.010, 1, 1.03),
        (1.000, 0, 1.00),
    ]
    for i, (zoom, dy, bright) in enumerate(variants):
        fr = _rounded_photo(SOURCE, zoom=zoom, dy=dy, brightness=bright)
        fr.save(os.path.join(AVATAR_DIR, f"speaking{i}.png"))

    print("Frames realistas generados en", AVATAR_DIR)


if __name__ == "__main__":
    generate()
