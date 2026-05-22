# test_fb_muestra.py
import os, django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

with open(".env", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())

django.setup()

from scraper_redes.run import scrapear_facebook_con_backend

urls = [
    "https://www.facebook.com/parroquianjesus",
    "https://www.facebook.com/SanBenitoParroquia",
    "https://www.facebook.com/BasilicaSantaRosaDeLima",
]

for url in urls:
    print(f"\n--- {url} ---")
    posts = scrapear_facebook_con_backend(url)
    print(f"Posts: {len(posts)}")
    for p in posts[:2]:
        print(
            f"  {p['post_id']} | {p['fecha'].strftime('%d/%m/%Y')} | img: {'✅' if p['imagen_url'] else '❌'} | {p['caption'][:50]}"
        )
