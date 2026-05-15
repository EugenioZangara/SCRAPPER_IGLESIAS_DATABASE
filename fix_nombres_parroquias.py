#!/usr/bin/env python
"""
Limpia nombres de parroquias que contienen URLs embebidas.

Ejemplo de problema: "CORAZON DE JESUS http://www.coriesu.com.ar"
Resultado esperado:  "CORAZON DE JESUS"

Uso: python fix_nombres_parroquias.py
"""

import os
import re
import sys

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from apps.iglesias.models import Parroquia

URL_RE = re.compile(r'\s*https?://\S.*$', re.IGNORECASE)


def nombre_limpio(nombre: str) -> str:
    return URL_RE.sub('', nombre).strip()


parroquias = Parroquia.objects.filter(nombre__iregex=r'https?://')

if not parroquias.exists():
    print("No se encontraron nombres con URLs embebidas. Nada que hacer.")
    sys.exit(0)

cambios = []
for p in parroquias.order_by('nombre'):
    limpio = nombre_limpio(p.nombre)
    if limpio != p.nombre:
        cambios.append((p, limpio))

if not cambios:
    print("No se encontraron cambios necesarios.")
    sys.exit(0)

print(f"Se encontraron {len(cambios)} registros con URLs en el nombre:\n")
print(f"  {'ID':>6}  {'NOMBRE ACTUAL':<60}  →  NOMBRE LIMPIO")
print(f"  {'-'*6}  {'-'*60}  {'':3}  {'-'*40}")
for p, limpio in cambios:
    print(f"  {p.pk:>6}  {p.nombre:<60}  →  {limpio}")

print()
resp = input(f"¿Aplicar {len(cambios)} cambio(s)? [s/N] ").strip().lower()
if resp != 's':
    print("Cancelado. No se modificó ningún registro.")
    sys.exit(0)

for p, limpio in cambios:
    p.nombre = limpio
    p.save(update_fields=["nombre"])
    print(f"  ✓ ID {p.pk}: guardado")

print(f"\n{len(cambios)} registro(s) actualizados correctamente.")
