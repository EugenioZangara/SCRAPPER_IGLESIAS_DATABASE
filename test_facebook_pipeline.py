# test_facebook_pipeline.py
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

posts = scrapear_facebook_con_backend("https://www.facebook.com/parroquianjesus")
print(f"\nPosts obtenidos: {len(posts)}")
for p in posts:
    print(
        f"  {p['post_id']} | {p['fecha'].strftime('%d/%m/%Y')} | img: {'✅' if p['imagen_url'] else '❌'} | caption: {p['caption'][:50]}"
    )
