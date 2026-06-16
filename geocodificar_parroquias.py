# -*- coding: utf-8 -*-
import os, django, time, httpx, re

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

with open(".env", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ[key.strip()] = value.strip()

django.setup()

from apps.iglesias.models import Parroquia


ABREVIATURAS = [
    (r'\bAV\.\s*',    'Avenida '),
    (r'\bGRAL\.\s*',  'General '),
    (r'\bDR\.\s*',    'Doctor '),
    (r'\bDRA\.\s*',   'Doctora '),
    (r'\bTTE\.\s*',   'Teniente '),
    (r'\bTT\.\s*',    'Teniente '),
    (r'\bCAP\.\s*',   'Capitán '),
    (r'\bCTE\.\s*',   'Comandante '),
    (r'\bCNEL\.\s*',  'Coronel '),
    (r'\bPJE\.\s*',   'Pasaje '),
    (r'\bPBRO\.\s*',  'Presbítero '),
    (r'\bMONS\.\s*',  'Monseñor '),
    (r'\bPTE\.\s*',   'Presidente '),
]


def limpiar_direccion(direccion: str) -> str:
    d = direccion.strip()
    # Eliminar referencia de cruce "E/M.ACOSTA Y M.CASTRO"
    d = re.sub(r'\s+[Ee]/.*$', '', d)
    # Eliminar sufijo con guion descriptivo: " - MANZ.8 CASA 1"
    d = re.sub(r'\s+-\s+\S.*$', '', d)
    # Eliminar número de lote secundario: "/3155"
    d = re.sub(r'/\d+', '', d)
    # Expandir abreviaturas (orden importa: TT. antes de T.)
    for pattern, repl in ABREVIATURAS:
        d = re.sub(pattern, repl, d, flags=re.IGNORECASE)
    # Normalizar espacios y title case
    d = ' '.join(d.split())
    return d.title()


def extraer_calle_numero(dir_limpia: str) -> tuple[str, str]:
    """Extrae ('Nombre De Calle', '1234') de una dirección limpia."""
    m = re.search(r'^(.+?)\s+(\d+)\s*$', dir_limpia.strip())
    if m:
        return m.group(1).strip(), m.group(2).strip()
    # Fallback: número en cualquier posición
    m = re.search(r'^(.+?)\s+(\d+)', dir_limpia.strip())
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return dir_limpia.strip(), ''


GOOGLE_API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY", "")


def geocodificar_google(dir_limpia: str, barrio: str, ciudad: str, provincia: str) -> tuple[float | None, float | None]:
    if not GOOGLE_API_KEY:
        return None, None
    contexto = ciudad or barrio or provincia or "Buenos Aires"
    partes = [p for p in [dir_limpia, barrio if barrio != contexto else None, contexto, "Argentina"] if p]
    address = ", ".join(partes)
    print(f"    [Google] {address}")
    try:
        resp = httpx.get(
            "https://maps.googleapis.com/maps/api/geocode/json",
            params={"address": address, "key": GOOGLE_API_KEY},
            timeout=10,
        )
        data = resp.json()
        if data.get("status") == "OK":
            loc = data["results"][0]["geometry"]["location"]
            return float(loc["lat"]), float(loc["lng"])
        print(f"    [Google] status: {data.get('status')} — {data.get('error_message', '')}")
    except Exception as e:
        print(f"    [Google] ERROR: {e}")
    return None, None


def nominatim_get(query: str) -> tuple[float | None, float | None]:
    try:
        resp = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "json", "limit": 1, "countrycodes": "ar"},
            headers={"User-Agent": "ParroGuia/1.0 geocodificacion"},
            timeout=10,
        )
        results = resp.json()
        if results:
            return float(results[0]["lat"]), float(results[0]["lon"])
    except Exception as e:
        print(f"    [Nominatim] ERROR: {e}")
    return None, None


def geocodificar_nominatim(dir_limpia: str, barrio: str, ciudad: str) -> tuple[float | None, float | None]:
    """Hasta 3 intentos con queries progresivamente más simples. 1.1s entre cada uno."""
    calle, numero = extraer_calle_numero(dir_limpia)

    intentos = []
    if barrio:
        intentos.append(f"{dir_limpia}, {barrio}, Buenos Aires, Argentina")
    intentos.append(f"{dir_limpia}, {ciudad}, Argentina")
    if numero:
        intentos.append(f"{calle} {numero}, {ciudad}, Argentina")
    elif calle != dir_limpia:
        intentos.append(f"{calle}, {ciudad}, Argentina")

    vistos = set()
    intentos_unicos = []
    for q in intentos:
        if q not in vistos:
            vistos.add(q)
            intentos_unicos.append(q)

    for n, query in enumerate(intentos_unicos, 1):
        if n > 1:
            time.sleep(1.1)
        print(f"    [Nominatim] Intento {n}/{len(intentos_unicos)}: {query}")
        lat, lng = nominatim_get(query)
        if lat and lng:
            print(f"    ✓ Nominatim éxito en intento {n}: {lat:.6f}, {lng:.6f}")
            return lat, lng

    return None, None


def geocodificar(p) -> tuple[float | None, float | None]:
    """Google Maps primero, Nominatim como fallback."""
    dir_limpia = limpiar_direccion(p.direccion or '')
    if not dir_limpia:
        print("    ✗ Dirección vacía tras limpieza")
        return None, None

    barrio   = p.barrio   or ''
    ciudad   = p.ciudad   or barrio or 'Buenos Aires'
    provincia = p.provincia or ''

    # --- Intento 1: Google Maps Geocoding API ---
    lat, lng = geocodificar_google(dir_limpia, barrio, ciudad, provincia)
    if lat and lng:
        print(f"    ✓ Google éxito: {lat:.6f}, {lng:.6f}")
        return lat, lng

    # --- Fallback: Nominatim con múltiples queries ---
    print(f"    → Fallback a Nominatim...")
    time.sleep(1.1)
    return geocodificar_nominatim(dir_limpia, barrio, ciudad)


parroquias = Parroquia.objects.filter(
    latitud__isnull=True,
    direccion__isnull=False,
).exclude(direccion="")

total = parroquias.count()
print(f"Geocodificando {total} parroquias sin coordenadas...\n")

ok = 0
sin_resultado = 0

for i, p in enumerate(parroquias, 1):
    print(f"[{i}/{total}] {p.nombre[:55]}")
    print(f"  Original : {p.direccion}")
    print(f"  Barrio: {p.barrio or '—'}  Ciudad: {p.ciudad or '—'}  Provincia: {p.provincia or '—'}")
    print(f"  Limpia   : {limpiar_direccion(p.direccion or '')}")

    lat, lng = geocodificar(p)
    if lat and lng:
        p.latitud = lat
        p.longitud = lng
        p.save(update_fields=["latitud", "longitud"])
        ok += 1
    else:
        print(f"    ✗ Sin resultado en ningún intento")
        sin_resultado += 1

    time.sleep(1.1)

print(f"\nResultado: {ok} geocodificadas, {sin_resultado} sin resultado de {total} total")
