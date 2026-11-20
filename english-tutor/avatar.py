from PIL import Image, ImageDraw, ImageFont

def _font(size, bold=True):
    for name in ("Segoe UI", "Arial", "Helvetica"):
        try:
            return ImageFont.truetype(f"C:/Windows/Fonts/{name}.ttf", size)
        except Exception:
            pass
    return ImageFont.load_default()

def draw_avatar(path, mouth=0.0, state="idle", size=360):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = cy = size // 2
    r = size // 2 - 12

    if state == "listening":
        glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        gd.ellipse([cx - r - 10, cy - r - 10, cx + r + 10, cy + r + 10],
                   fill=(96, 165, 250, 70))
        img = Image.alpha_composite(glow, img)
        d = ImageDraw.Draw(img)

    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 255, 255, 255),
              outline=(200, 210, 230, 255), width=6)

    eye_r = max(4, int(r * 0.07))
    d.ellipse([cx - r * 0.32 - eye_r, cy - r * 0.22 - eye_r,
               cx - r * 0.32 + eye_r, cy - r * 0.22 + eye_r], fill=(90, 90, 110, 255))
    d.ellipse([cx + r * 0.32 - eye_r, cy - r * 0.22 - eye_r,
               cx + r * 0.32 + eye_r, cy - r * 0.22 + eye_r], fill=(90, 90, 110, 255))

    mw = int(r * 0.34)
    mh = max(2, int(mouth * r * 0.20))
    d.ellipse([cx - mw // 2, cy + int(r * 0.10) - mh // 2,
               cx + mw // 2, cy + int(r * 0.10) + mh // 2], fill=(120, 90, 90, 255))

    f = _font(int(r * 0.55), bold=True)
    bbox = d.textbbox((0, 0), "E", font=f)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text((cx - tw // 2, cy - th // 2 - int(r * 0.05)), "E", font=f,
           fill=(255, 255, 255, 255))

    img.save(path)

if __name__ == "__main__":
    import os
    out = os.path.join(os.path.dirname(__file__), "data", "avatar")
    os.makedirs(out, exist_ok=True)
    draw_avatar(os.path.join(out, "idle.png"), 0.0, "idle")
    draw_avatar(os.path.join(out, "listening.png"), 0.0, "listening")
    for i, m in enumerate([0.3, 0.6, 1.0, 0.6, 0.3]):
        draw_avatar(os.path.join(out, f"speaking{i}.png"), m, "speaking")
    print("Avatar frames saved to", out)