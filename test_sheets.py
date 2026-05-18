import os, django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

with open(".env") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())

django.setup()

from apps.iglesias.models import Evento
from apps.iglesias.sheets import exportar_evento_a_sheets

evento = Evento.objects.filter(verificado=True).first()
if not evento:
    evento = Evento.objects.first()

if evento:
    print(f"Exportando: {evento.titulo} — {evento.parroquia.nombre}")
    resultado = exportar_evento_a_sheets(evento)
    print(f'Resultado: {"OK" if resultado else "ERROR"}')
else:
    print("No hay eventos en la DB")
