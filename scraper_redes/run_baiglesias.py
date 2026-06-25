import sys
import os
import time
import random

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django

django.setup()

from apps.iglesias.models import Parroquia, InfoBaiglesias, HorarioMisa
from scraper_redes.baiglesias import scrapear_baiglesias


def procesar_parroquia(parroquia) -> bool:
    """
    Scrapea la página de baiglesias de una parroquia y persiste la info.
    Retorna True si tuvo éxito.
    """
    url = parroquia.sitio_web
    resultado = scrapear_baiglesias(url)

    if not resultado:
        return False

    # Crear o actualizar InfoBaiglesias
    info, _ = InfoBaiglesias.objects.update_or_create(
        parroquia=parroquia,
        defaults={
            "direccion_completa": resultado["direccion_completa"],
            "como_llegar": resultado["como_llegar"],
            "url_scrapeada": url,
        },
    )

    # Borrar horarios anteriores y recrear (solo si no está gestionado manualmente)
    if not parroquia.gestionado_por_parroquia:
        HorarioMisa.objects.filter(parroquia=parroquia).delete()
        for h in resultado["horarios"]:
            HorarioMisa.objects.create(
                parroquia=parroquia,
                dias=h["dias"],
                horarios=h["horarios"],
                nota=h.get("nota"),
            )
    else:
        print(f"  ⏭  Horarios omitidos — parroquia gestionada manualmente")

    print(f"  ✅ Info guardada — {len(resultado['horarios'])} horarios")
    if resultado["direccion_completa"]:
        print(f"     Dirección : {resultado['direccion_completa'][:60]}")
    if resultado["como_llegar"]:
        print(f"     Cómo llegar: {resultado['como_llegar'][:60]}")
    for h in resultado["horarios"]:
        print(f"     {h['dias']}: {h['horarios']}")

    return True


def main():
    parroquias = Parroquia.objects.filter(
        sitio_web__icontains="baiglesias.com"
    ).order_by("nombre")

    total = parroquias.count()
    print(f"=== Scraper BAIglesias ===")
    print(f"Parroquias con web baiglesias.com: {total}\n")

    exitosos = 0
    errores = 0

    for i, parroquia in enumerate(parroquias, 1):
        print(f"--- [{i}/{total}] {parroquia.nombre} ---")
        try:
            ok = procesar_parroquia(parroquia)
            if ok:
                exitosos += 1
            else:
                errores += 1
        except Exception as e:
            print(f"  ERROR inesperado: {e}")
            errores += 1

        if i < total:
            espera = random.randint(3, 7)
            print(f"  Esperando {espera}s...")
            time.sleep(espera)

    print(f"\n=== RESUMEN ===")
    print(f"Exitosos: {exitosos}/{total}")
    print(f"Errores : {errores}/{total}")


main()
