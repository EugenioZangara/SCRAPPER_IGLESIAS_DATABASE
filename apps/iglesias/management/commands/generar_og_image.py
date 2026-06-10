import math
import os
from pathlib import Path

from django.core.management.base import BaseCommand

STATIC_IMG = Path(__file__).resolve().parent.parent.parent / "static" / "iglesias" / "img"
OUT_PATH = STATIC_IMG / "og_parroguia.png"
LOGO_PATH = STATIC_IMG / "parroguia_logo.png"

W, H = 1200, 630

# Colores
C1 = (0x14, 0x31, 0x5E)  # #14315E
C2 = (0x0E, 0x26, 0x47)  # #0E2647
GOLD = (242, 160, 7, 255)
WHITE = (255, 255, 255, 255)
WHITE_60 = (255, 255, 255, 153)


def _lerp(a, b, t):
    return int(a + (b - a) * t)


def _get_font(size, bold=False):
    from PIL import ImageFont

    candidates = []
    if bold:
        candidates = [
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/Arial_Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        ]
    else:
        candidates = [
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/Arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
        ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


class Command(BaseCommand):
    help = "Genera og_parroguia.png (1200×630) para previews de WhatsApp/redes sociales"

    def handle(self, *args, **options):
        try:
            from PIL import Image, ImageDraw, ImageFont  # noqa: F401
        except ImportError:
            self.stderr.write(self.style.ERROR(
                "Pillow no está instalado. Ejecutar: pip install Pillow"
            ))
            return

        from PIL import Image, ImageDraw

        # ── 1. Fondo con gradiente horizontal ──────────────────────────────
        img = Image.new("RGBA", (W, H))
        draw = ImageDraw.Draw(img)
        for x in range(W):
            t = x / (W - 1)
            r = _lerp(C1[0], C2[0], t)
            g = _lerp(C1[1], C2[1], t)
            b = _lerp(C1[2], C2[2], t)
            draw.line([(x, 0), (x, H)], fill=(r, g, b, 255))

        # ── 2. Franjas onduladas decorativas ───────────────────────────────
        wave = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        wd = ImageDraw.Draw(wave)

        def wave_pts(base_y, amplitude, period, phase, bottom=H):
            pts = [(0, bottom)]
            for x in range(0, W + 10, 6):
                y = base_y + int(amplitude * math.sin(x * 2 * math.pi / period + phase))
                pts.append((x, y))
            pts.append((W, bottom))
            return pts

        wd.polygon(wave_pts(480, 28, 780, 0), fill=(255, 255, 255, 26))
        wd.polygon(wave_pts(520, 18, 560, 1.2), fill=(255, 255, 255, 16))
        img = Image.alpha_composite(img, wave)
        draw = ImageDraw.Draw(img)

        # ── 3. Logo ────────────────────────────────────────────────────────
        logo_size = 160
        logo_x, logo_y = 80, (H - logo_size) // 2  # 235

        if LOGO_PATH.exists():
            from PIL import Image as PILImage
            logo = PILImage.open(LOGO_PATH).convert("RGBA").resize(
                (logo_size, logo_size), PILImage.LANCZOS
            )
            # Máscara circular
            mask = PILImage.new("L", (logo_size, logo_size), 0)
            from PIL import ImageDraw as ID2
            ID2.Draw(mask).ellipse([0, 0, logo_size - 1, logo_size - 1], fill=255)
            # Halo suave detrás del logo
            cx, cy = logo_x + logo_size // 2, logo_y + logo_size // 2
            r = logo_size // 2 + 8
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 255, 255, 30))
            # Pegar logo con máscara circular
            buf = PILImage.new("RGBA", (logo_size, logo_size), (0, 0, 0, 0))
            buf.paste(logo, mask=mask)
            img.paste(buf, (logo_x, logo_y), buf)
            draw = ImageDraw.Draw(img)
        else:
            self.stdout.write(self.style.WARNING(f"Logo no encontrado: {LOGO_PATH}"))

        # ── 4. Textos ──────────────────────────────────────────────────────
        tx = 300   # x de los textos
        ty_title = 210
        ty_sub = 318
        ty_url = 382

        font_title = _get_font(80, bold=True)
        font_sub = _get_font(38)
        font_url = _get_font(26)

        draw.text((tx, ty_title), "ParroGuía", font=font_title, fill=WHITE)
        draw.text((tx, ty_sub), "Encontrá tu próxima misa a un click", font=font_sub, fill=GOLD)
        draw.text((tx, ty_url), "parroquias.com.ar", font=font_url, fill=WHITE_60)

        # ── 5. Guardar PNG ─────────────────────────────────────────────────
        OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        img.convert("RGB").save(str(OUT_PATH), "PNG", optimize=True)
        self.stdout.write(self.style.SUCCESS(f"OK Imagen generada: {OUT_PATH}"))
        self.stdout.write("  Asegurate de correr 'collectstatic' antes del deploy.")
