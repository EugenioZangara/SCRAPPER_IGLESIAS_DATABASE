"""
Sube las imágenes locales de imagenes_parroquias/ a ImageKit y
actualiza Parroquia.imagen_url en la base de datos.

Uso:
    python subir_imagenes_imagekit.py            # salta si ya tiene imagen_url
    python subir_imagenes_imagekit.py --forzar   # re-sube aunque ya tenga imagen_url
"""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

load_dotenv()

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from apps.iglesias.models import Parroquia
from imagekitio import ImageKit

IMAGEKIT_PRIVA_KEY = os.environ["IMAGEKIT_PRIVA_KEY"]

CARPETA_BASE = Path("imagenes_parroquias")
FORZAR = "--forzar" in sys.argv

# v5: solo private_key; url_endpoint no se usa en uploads
ik = ImageKit(private_key=IMAGEKIT_PRIVA_KEY)


def subir_imagen(archivo: Path, provincia_slug: str) -> str:
    with open(archivo, "rb") as f:
        result = ik.files.upload(
            file=f,
            file_name=archivo.name,
            folder=f"/parroquias/{provincia_slug}/",
            use_unique_file_name=False,
            overwrite_file=True,
        )
    return result.url


def main():
    stats = {"subidas": 0, "skipped": 0, "sin_parroquia": 0, "errores": 0}

    archivos = sorted(CARPETA_BASE.rglob("*.jpg"))
    total = len(archivos)
    print(f"\nImágenes encontradas : {total}")
    print(f"Modo                 : {'FORZAR re-subida' if FORZAR else 'saltar si ya tiene imagen_url'}\n")

    for i, archivo in enumerate(archivos, 1):
        nombre = archivo.name  # ej: 581__santuario-nuestra-senora.jpg
        partes = nombre.split("__", 1)

        if len(partes) != 2 or not partes[0].isdigit():
            print(f"[{i}/{total}] SKIP nombre inválido: {nombre}")
            stats["errores"] += 1
            continue

        pk = int(partes[0])
        provincia_slug = archivo.parent.name  # subdirectorio = slug de provincia

        try:
            p = Parroquia.objects.get(pk=pk)
        except Parroquia.DoesNotExist:
            print(f"[{i}/{total}] pk={pk} — no existe en BD ({nombre})")
            stats["sin_parroquia"] += 1
            continue

        if p.imagen_url and "ik.imagekit.io" in p.imagen_url and not FORZAR:
            stats["skipped"] += 1
            continue

        try:
            url = subir_imagen(archivo, provincia_slug)
            Parroquia.objects.filter(pk=pk).update(imagen_url=url)
            print(f"[{i}/{total}] OK pk={pk} {p.nombre[:40]} → {url}")
            stats["subidas"] += 1
            time.sleep(0.3)
        except Exception as e:
            print(f"[{i}/{total}] ERROR pk={pk} {p.nombre[:40]}: {e}")
            stats["errores"] += 1
            time.sleep(1)

    print(f"\n{'━'*40}")
    print(f"Subidas OK       : {stats['subidas']}")
    print(f"Skipped          : {stats['skipped']}")
    print(f"Sin parroquia BD : {stats['sin_parroquia']}")
    print(f"Errores          : {stats['errores']}")
    print(f"{'━'*40}")


if __name__ == "__main__":
    main()
