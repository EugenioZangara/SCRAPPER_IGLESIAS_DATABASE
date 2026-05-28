import os, django, time, httpx

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

with open(".env", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ[key.strip()] = value.strip()

django.setup()

from apps.iglesias.models import Parroquia


def geocodificar(direccion: str, barrio: str = "") -> tuple:
    """Consulta Nominatim para obtener lat/lng de una dirección."""
    query = f"{direccion}, {barrio}, Buenos Aires, Argentina"
    try:
        resp = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q": query,
                "format": "json",
                "limit": 1,
                "countrycodes": "ar",
            },
            headers={"User-Agent": "ParroGuia/1.0 geocodificacion"},
            timeout=10,
        )
        results = resp.json()
        if results:
            return float(results[0]["lat"]), float(results[0]["lon"])
    except Exception as e:
        print(f"  ERROR: {e}")
    return None, None


parroquias = Parroquia.objects.filter(
    latitud__isnull=True,
    direccion__isnull=False
).exclude(direccion="")

total = parroquias.count()
print(f"Geocodificando {total} parroquias...")

ok = 0
sin_resultado = 0

for i, p in enumerate(parroquias, 1):
    print(f"[{i}/{total}] {p.nombre[:40]} — {p.direccion}")
    lat, lng = geocodificar(p.direccion, p.barrio or "")
    if lat and lng:
        p.latitud = lat
        p.longitud = lng
        p.save(update_fields=["latitud", "longitud"])
        print(f"  ✓ {lat}, {lng}")
        ok += 1
    else:
        print(f"  ✗ Sin resultado")
        sin_resultado += 1
    # Nominatim pide máximo 1 request/segundo
    time.sleep(1.1)

print(f"\nResultado: {ok} geocodificadas, {sin_resultado} sin resultado")
