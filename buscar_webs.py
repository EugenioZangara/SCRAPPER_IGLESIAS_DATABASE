import os, django, httpx, time
from urllib.parse import quote

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
with open(".env", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()
django.setup()

from apps.iglesias.models import Parroquia

sin_web = Parroquia.objects.filter(sitio_web__isnull=True).order_by("nombre")
print(f"Parroquias sin web: {sin_web.count()}\n")

for p in sin_web:
    barrio = p.barrio or ""
    # Construir query de búsqueda
    query = f"{p.nombre} parroquia {barrio} Buenos Aires"
    url_busqueda = f"https://www.google.com/search?q={quote(query)}"
    print(f"{p.nombre[:50]}")
    print(f"  Barrio: {barrio or 'sin barrio'}")
    print(f"  Buscar: {url_busqueda}")
    print()
