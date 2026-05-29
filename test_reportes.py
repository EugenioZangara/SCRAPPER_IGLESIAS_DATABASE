# test_reportes.py
import os, django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

with open(".env", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()

django.setup()

from apps.iglesias.models import ReporteHorario

for r in ReporteHorario.objects.all().order_by("-creado_en")[:5]:
    print(f"ID:{r.pk} fuente:{r.fuente} url_post:{r.url_post or 'VACÍO'}")
    print(f"  parroquia: {r.parroquia.nombre[:40]}")
    print(f"  imagen_url: {'SI' if r.imagen_url else 'NO'}")
    print()
