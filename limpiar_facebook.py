# limpiar_facebook.py
import os, django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

with open(".env", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())

django.setup()

from apps.iglesias.models import RedSocial
from urllib.parse import urlparse

# 1. Desactivar cuentas que NO son páginas parroquiales
desactivar = [
    "groups/cristobreroretiro",  # grupo, no página
    "wwwbarriadacomar",  # sitio de barriada.com
    "FerraBruma-100189012714433",  # no es la parroquia
    "talleresdelsagrado",  # taller, no parroquia
    "duchasdelsagrado",  # servicio, no parroquia
    "ateneodelsagrado",  # ateneo, no parroquia
    "comunidadguia.sagradocorazon",  # comunidad, no parroquia
    "Monasterio-Santa-Catalina-de-Siena-108045634135120",  # monasterio duplicado
    "p/Parroquia-Santa-Clara-100064764094351",  # duplicado de pquiastaclaradeasis
    "Santuario-San-Pantale%C3%B3n-262033157239139",  # duplicado codificado
    "parroquiaporres",  # duplicado de parroquia.porres
]

desactivadas = 0
for pattern in desactivar:
    qs = RedSocial.objects.filter(tipo="facebook", url__icontains=pattern)
    count = qs.update(activo=False)
    if count:
        print(f"  Desactivada: {pattern} ({count})")
        desactivadas += count

print(f"\nTotal desactivadas: {desactivadas}")

# 2. Limpiar URLs con parámetros
print("\nLimpiando URLs con parámetros...")
redes = RedSocial.objects.filter(tipo="facebook", activo=True)
limpiadas = 0
for r in redes:
    parsed = urlparse(r.url)
    # Eliminar query string y fragment
    url_limpia = f"https://www.facebook.com{parsed.path.rstrip('/')}"
    # Normalizar m.facebook.com → www.facebook.com
    url_limpia = url_limpia.replace("m.facebook.com", "www.facebook.com")
    if url_limpia != r.url:
        print(f"  {r.url[:60]}")
        print(f"  → {url_limpia}")
        r.url = url_limpia
        r.save(update_fields=["url"])
        limpiadas += 1

print(f"\nURLs limpiadas: {limpiadas}")

# 3. Verificar en bloque las páginas claramente parroquiales
verificar = [
    "parroquianjesus",
    "parroquiabalvanera",
    "SantuarioFatima",
    "pfatimasoldati",
    "comunicacionparroquiaguadalupe",
    "DonOrioneAr",
    "ParroMisericordia",
    "parroquiadolores",
    "LujanPorteno",
    "elatriodelcarmen",
    "basilicadelpilar",
    "santuariopompeya",
    "nuestrasenoradel.rosariodelmilagro",
    "basilicadelsocorro",
    "parroquia.emigrantes",
    "resurreccion.org.ar",
    "sagradaeucaristia",
    "sagradobarracas",
    "SanBenitoParroquia",
    "Santuario-San-Cayetano-Liniers-600975333261464",
    "Parroquiascysd",
    "calasanzsandoval",
    "sanjosedeflores",
    "ParroquiaSanJuanBoscoColegiales",
    "ParroquiaSanJuanDiegoCuauhtlatoatzin",
    "parroquia.porres",
    "parroquia.san.roque.424991",
    "SantaCatalinaPastoral",
    "pquiastaclaradeasis",
    "parroquiacabrinioficial",
    "SantaLuciaDePalermo",
    "santaluciabarracas",
    "parroquiabetaniaBsAs",
    "santamariadelosangelescoghlan",
    "BasilicaSantaRosaDeLima",
    "parroquiasantiagoapostol",
    "PquiadelSantisimoRedentor",
    "parroquiasoledademaria",
    "caacupebarracas",
    "virgenybasilicalujan",
    "parroquiavilla20",
    "jesus.dulcisimo",
    "parroquiacabrinioficial",
    "calasanzcaballito",
    "santuariomedallamilagrosa",
    "Parroquia-Cristo-Rey-Bs-As-101962221555759",
    "SanBenitoParroquia",
    "santuariopompeya",
]

verificadas = 0
for pattern in verificar:
    qs = RedSocial.objects.filter(
        tipo="facebook", activo=True, verificado=False, url__icontains=pattern
    )
    count = qs.update(verificado=True)
    if count:
        verificadas += count

print(f"\nVerificadas: {verificadas}")

# Resumen final
total = RedSocial.objects.filter(tipo="facebook", activo=True).count()
verif = RedSocial.objects.filter(tipo="facebook", activo=True, verificado=True).count()
print(f"\nEstado final Facebook:")
print(f"  Activas    : {total}")
print(f"  Verificadas: {verif}")
print(f"  Pendientes : {total - verif}")
print()
print("Verificadas:")
for r in RedSocial.objects.filter(tipo="facebook", activo=True, verificado=True):
    print(f"  {r.parroquia.nombre[:40]:40} {r.url}")
