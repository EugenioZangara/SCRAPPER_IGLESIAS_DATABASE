import os
import sys
import time
import django
import requests
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

from dotenv import load_dotenv
load_dotenv()
django.setup()

from apps.iglesias.models import Parroquia

API_KEY = os.environ['GOOGLE_PLACES_API_KEY']
CARPETA_BASE = Path('imagenes_parroquias')
CARPETA_BASE.mkdir(exist_ok=True)

HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; ParroGuia-bot/1.0)'}

# ── helpers de nombre/carpeta ─────────────────────────────────────────────────

def nombre_archivo(parroquia):
    import unicodedata, re
    nombre = parroquia.nombre.lower()
    nombre = unicodedata.normalize('NFKD', nombre).encode('ascii', 'ignore').decode()
    nombre = re.sub(r'[^a-z0-9]+', '-', nombre).strip('-')[:60]
    return f"{parroquia.pk}__{nombre}.jpg"

def subcarpeta(parroquia):
    import unicodedata, re
    prov = (parroquia.provincia or 'sin-provincia').lower()
    prov = unicodedata.normalize('NFKD', prov).encode('ascii', 'ignore').decode()
    prov = re.sub(r'[^a-z0-9]+', '-', prov).strip('-')
    carpeta = CARPETA_BASE / prov
    carpeta.mkdir(exist_ok=True)
    return carpeta

# ── Google Places ─────────────────────────────────────────────────────────────

def buscar_place_id(parroquia):
    """
    Busca el place_id en Google Places usando nombre + dirección.
    Intenta primero con lat/lng (más preciso), luego con texto.
    """
    # Intento 1: Nearby Search si tiene coordenadas
    if parroquia.latitud and parroquia.longitud:
        url = 'https://maps.googleapis.com/maps/api/place/nearbysearch/json'
        params = {
            'location': f"{parroquia.latitud},{parroquia.longitud}",
            'radius': 100,
            'keyword': parroquia.nombre,
            'type': 'church',
            'language': 'es',
            'key': API_KEY,
        }
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        if data.get('results'):
            place = data['results'][0]
            return place['place_id'], place.get('photos', [])

    # Intento 2: Text Search con nombre + dirección
    query_parts = [parroquia.nombre]
    if parroquia.direccion:
        query_parts.append(parroquia.direccion)
    if parroquia.ciudad:
        query_parts.append(parroquia.ciudad)
    elif parroquia.barrio:
        query_parts.append(parroquia.barrio)
    query_parts.append('Argentina')

    url = 'https://maps.googleapis.com/maps/api/place/textsearch/json'
    params = {
        'query': ', '.join(query_parts),
        'type': 'church',
        'language': 'es',
        'key': API_KEY,
    }
    resp = requests.get(url, params=params, timeout=10)
    data = resp.json()
    if data.get('results'):
        place = data['results'][0]
        return place['place_id'], place.get('photos', [])

    return None, []


def obtener_foto_url(photo_reference, max_width=800):
    """Retorna la URL directa de descarga de la foto."""
    return (
        f"https://maps.googleapis.com/maps/api/place/photo"
        f"?maxwidth={max_width}&photo_reference={photo_reference}&key={API_KEY}"
    )


def descargar_foto(photo_reference):
    """Descarga la foto y retorna los bytes. None si falla."""
    try:
        url = obtener_foto_url(photo_reference)
        resp = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
        resp.raise_for_status()
        if 'image' not in resp.headers.get('content-type', ''):
            return None
        return resp.content
    except Exception as e:
        print(f"         ERROR descarga: {e}")
        return None


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    # Procesar parroquias sin imagen todavía
    # Para reprocesar todas, quitar el filtro imagen_url=''
    parroquias = Parroquia.objects.filter(imagen_url='').order_by('provincia', 'pk')
    total = parroquias.count()
    print(f"\nParroquias sin imagen: {total}")
    print(f"Destino local: {CARPETA_BASE.resolve()}\n")

    ok = 0
    sin_place = 0
    sin_foto = 0
    errores = 0
    existentes = 0

    for i, p in enumerate(parroquias, 1):
        carpeta = subcarpeta(p)
        archivo = carpeta / nombre_archivo(p)

        if archivo.exists():
            existentes += 1
            # Si ya está descargada pero imagen_url está vacío, actualizar el campo
            # (útil si el script se interrumpió antes de guardar en DB)
            Parroquia.objects.filter(pk=p.pk).update(imagen_url=f"LOCAL:{archivo}")
            print(f"[{i}/{total}] SKIP (ya en disco) {archivo.name}")
            continue

        print(f"[{i}/{total}] {p.nombre} | {p.ciudad or p.barrio or ''} ({p.provincia or 'sin prov'})")

        # Buscar en Google Places
        try:
            place_id, photos = buscar_place_id(p)
        except Exception as e:
            print(f"         ERROR Places API: {e}")
            errores += 1
            time.sleep(1)
            continue

        if not place_id:
            print(f"         SIN MATCH en Google Places")
            sin_place += 1
            time.sleep(0.3)
            continue

        if not photos:
            print(f"         Place encontrado ({place_id}) pero SIN FOTOS")
            sin_foto += 1
            time.sleep(0.3)
            continue

        # Tomar la primera foto
        photo_reference = photos[0]['photo_reference']
        print(f"         Place: {place_id} | {len(photos)} foto(s) disponibles")

        data = descargar_foto(photo_reference)
        if not data:
            errores += 1
            time.sleep(0.5)
            continue

        # Guardar en disco como JPEG
        try:
            from PIL import Image
            from io import BytesIO
            img = Image.open(BytesIO(data)).convert('RGB')
            img.save(archivo, 'JPEG', quality=85, optimize=True)
            size_kb = archivo.stat().st_size // 1024
            print(f"         OK → {archivo.name} ({size_kb} KB)")

            # Guardar URL original de Google en imagen_url
            # (cuando subas a Render, reemplazarás con la URL del servidor)
            url_google = obtener_foto_url(photo_reference)
            Parroquia.objects.filter(pk=p.pk).update(imagen_url=url_google)
            ok += 1
        except Exception as e:
            print(f"         ERROR guardando imagen: {e}")
            errores += 1

        # Pausa para respetar rate limits de Google
        time.sleep(0.5)

    print(f"\n━━━ RESUMEN ━━━")
    print(f"Fotos descargadas : {ok}")
    print(f"Ya en disco       : {existentes}")
    print(f"Sin match Places  : {sin_place}")
    print(f"Place sin fotos   : {sin_foto}")
    print(f"Errores           : {errores}")
    print(f"Total procesadas  : {total}")
    print(f"\nCarpeta: {CARPETA_BASE.resolve()}")

if __name__ == '__main__':
    main()
