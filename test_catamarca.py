import os, django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
with open(".env", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()
django.setup()

from apps.iglesias.models import Parroquia, HorarioMisa

pqs = Parroquia.objects.filter(provincia="Catamarca")
print(f"Parroquias: {pqs.count()}")
p = pqs.first()
print(f"Ejemplo: {p.nombre}")
print(f"  Ciudad: {p.ciudad}")
print(f"  Provincia: {p.provincia}")
print(f"  Dirección: {p.direccion}")
horarios = HorarioMisa.objects.filter(parroquia=p)
print(f"  Horarios: {horarios.count()}")
dias = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
for h in horarios:
    print(f"    {dias[h.dia_semana]}: {h.horarios}")
