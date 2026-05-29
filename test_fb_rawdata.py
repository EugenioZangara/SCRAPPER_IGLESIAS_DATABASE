import os, django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

with open(".env", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()

django.setup()

from apps.iglesias.models import PostParroquia

posts_fb = PostParroquia.objects.filter(red_social="facebook").order_by("-creado_en")[
    :3
]

for p in posts_fb:
    url_post = p.raw_data.get("url_post", "NO TIENE") if p.raw_data else "sin raw_data"
    keys = list(p.raw_data.keys()) if p.raw_data else []
    print(f"{p.post_id}")
    print(f"  url_post: {url_post}")
    print(f"  keys: {keys}")
    print()
