"""
Segunda pasada de fotos: para parroquias con sin_imagen_valida en el cache,
intenta fotos de Google Places a partir del índice 5 (los índices 1-4 ya
fueron probados por scraper_verificar_imagenes.py).
"""

import os
import sys
import time
import json
import django
import requests
import base64
from pathlib import Path
from io import BytesIO

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

from dotenv import load_dotenv

load_dotenv()
django.setup()

from apps.iglesias.models import Parroquia
from PIL import Image

GOOGLE_PLACES_API_KEY = os.environ["GOOGLE_PLACES_API_KEY"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]
CARPETA_BASE = Path("imagenes_parroquias")
CARPETA_RECHAZADAS = Path("imagenes_rechazadas")
CARPETA_RECHAZADAS.mkdir(exist_ok=True)
CACHE_FILE = Path("verificacion_cache.json")

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ParroGuia-bot/1.0)"}

# La verificación original prueba fotos en índices 1-4 (salta el 0).
# Acá empezamos desde el índice 5 para no repetir.
FOTO_INICIO = 5
FOTO_FIN = 12  # probar hasta índice 12


def cargar_cache():
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text())
    return {}


def guardar_cache(cache):
    CACHE_FILE.write_text(json.dumps(cache, indent=2, ensure_ascii=False))


def nombre_archivo(parroquia):
    import unicodedata, re

    nombre = parroquia.nombre.lower()
    nombre = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode()
    nombre = re.sub(r"[^a-z0-9]+", "-", nombre).strip("-")[:60]
    return f"{parroquia.pk}__{nombre}.jpg"


def subcarpeta(parroquia):
    import unicodedata, re

    prov = (parroquia.provincia or "sin-provincia").lower()
    prov = unicodedata.normalize("NFKD", prov).encode("ascii", "ignore").decode()
    prov = re.sub(r"[^a-z0-9]+", "-", prov).strip("-")
    carpeta = CARPETA_BASE / prov
    carpeta.mkdir(exist_ok=True)
    return carpeta


PROMPT_VERIFICACION = """Analizá esta imagen y respondé SOLO con un JSON, sin texto adicional, sin markdown.

El JSON debe tener exactamente esta estructura:
{
  "es_iglesia": true/false,
  "tiene_personas": true/false,
  "confianza": "alta"/"media"/"baja",
  "descripcion": "descripción breve de lo que se ve en la imagen (máximo 15 palabras)",
  "motivo_rechazo": "razón si es_iglesia es false o tiene_personas es true, sino null"
}

Criterios para es_iglesia = true:
- Se ve la fachada exterior de una iglesia, parroquia, capilla o catedral
- Se ve el interior de una iglesia (nave, altar, bancas, vitrales)
- Se ve una torre campanario o cúpula religiosa claramente identificable

Criterios para es_iglesia = false:
- Foto de un evento (misa, procesión, boda, bautismo, reunión con personas)
- Foto de comida, flores, decoración sin edificio visible
- Imagen genérica, logo, afiche o flyer
- Foto de una calle o edificio que no es una iglesia
- Imagen en negro, borrosa o ilegible

Criterios para tiene_personas = true:
- Se ven rostros o cuerpos reconocibles de personas reales fotografiadas
- Hay personas en primer o segundo plano (sacerdotes, feligreses, grupos, individuos)
- Foto de un evento aunque el edificio sea visible al fondo

Criterios para tiene_personas = false (NO cuenta como personas):
- Pinturas, murales o mosaicos religiosos con figuras (aunque tengan rostros)
- Vitrales con imágenes de santos o escenas bíblicas
- Esculturas, imágenes o estatuas religiosas (Virgen, Cristo, santos)
- Personas diminutas e irreconocibles que aparecen de fondo por escala del edificio
"""

import groq

groq_client = groq.Groq(api_key=GROQ_API_KEY)


def verificar_con_groq(imagen_path, reintentos=3):
    try:
        img = Image.open(imagen_path).convert("RGB")
        img.thumbnail((1024, 1024), Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, "JPEG", quality=85)
        img_b64 = base64.b64encode(buf.getvalue()).decode()

        for intento in range(reintentos):
            try:
                response = groq_client.chat.completions.create(
                    model="meta-llama/llama-4-scout-17b-16e-instruct",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": PROMPT_VERIFICACION},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{img_b64}"
                                    },
                                },
                            ],
                        }
                    ],
                    temperature=0.1,
                    max_tokens=200,
                )
                texto = response.choices[0].message.content.strip()
                texto = texto.replace("```json", "").replace("```", "").strip()
                return json.loads(texto)

            except groq.RateLimitError:
                espera = 30 * (intento + 1)
                print(f"         Rate limit Groq — esperando {espera}s...")
                time.sleep(espera)
                continue
            except Exception as e:
                print(f"         ERROR Groq intento {intento+1}: {e}")
                time.sleep(5)
                continue

        print(f"         ERROR: se agotaron los reintentos")
        return None

    except Exception as e:
        print(f"         ERROR procesando imagen: {e}")
        return None


def buscar_fotos_places(parroquia):
    """Devuelve la lista completa de photo_references de Google Places."""
    try:
        if parroquia.latitud and parroquia.longitud:
            url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
            params = {
                "location": f"{parroquia.latitud},{parroquia.longitud}",
                "radius": 100,
                "keyword": parroquia.nombre,
                "type": "church",
                "language": "es",
                "key": GOOGLE_PLACES_API_KEY,
            }
            resp = requests.get(url, params=params, timeout=10)
            data = resp.json()
            if data.get("results") and data["results"][0].get("photos"):
                return [p["photo_reference"] for p in data["results"][0]["photos"]]

        query_parts = [parroquia.nombre]
        if parroquia.direccion:
            query_parts.append(parroquia.direccion)
        if parroquia.ciudad:
            query_parts.append(parroquia.ciudad)
        query_parts.append("Argentina")

        url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
        params = {
            "query": ", ".join(query_parts),
            "type": "church",
            "language": "es",
            "key": GOOGLE_PLACES_API_KEY,
        }
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        if data.get("results") and data["results"][0].get("photos"):
            return [p["photo_reference"] for p in data["results"][0]["photos"]]

    except Exception as e:
        print(f"         ERROR Places: {e}")

    return []


def descargar_foto_places(photo_reference):
    try:
        url = (
            f"https://maps.googleapis.com/maps/api/place/photo"
            f"?maxwidth=800&photo_reference={photo_reference}&key={GOOGLE_PLACES_API_KEY}"
        )
        resp = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
        resp.raise_for_status()
        if "image" not in resp.headers.get("content-type", ""):
            return None
        return resp.content
    except Exception:
        return None


def guardar_imagen(data, archivo):
    img = Image.open(BytesIO(data)).convert("RGB")
    img.save(archivo, "JPEG", quality=85, optimize=True)


def main():
    cache = cargar_cache()

    # Solo parroquias con sin_imagen_valida que aún no fueron procesadas en esta pasada
    RESULTADOS_SKIP = {"ok", "ok_alternativa", "ok_segunda_pasada", "segunda_pasada_sin_imagen"}
    pks_sin_imagen = [
        int(pk)
        for pk, v in cache.items()
        if v.get("resultado") not in RESULTADOS_SKIP
    ]

    if not pks_sin_imagen:
        print("No hay parroquias con sin_imagen_valida en el cache.")
        return

    parroquias = Parroquia.objects.filter(pk__in=pks_sin_imagen).order_by("provincia", "pk")
    total = parroquias.count()

    print(f"\nParroquias a reintentar: {total}")
    print(f"Buscando fotos en índices {FOTO_INICIO}–{FOTO_FIN - 1}\n")

    stats = {
        "ok": 0,
        "sin_fotos_suficientes": 0,
        "todas_rechazadas": 0,
        "error_places": 0,
    }

    for i, p in enumerate(parroquias, 1):
        cache_key = str(p.pk)
        carpeta = subcarpeta(p)
        archivo = carpeta / nombre_archivo(p)

        print(f"[{i}/{total}] {p.nombre} | {p.ciudad or p.barrio or ''}")

        refs = buscar_fotos_places(p)
        candidatas = refs[FOTO_INICIO:FOTO_FIN]

        if not candidatas:
            print(f"         Sin fotos en índices {FOTO_INICIO}+  (total disponibles: {len(refs)})")
            cache[cache_key] = {"resultado": "segunda_pasada_sin_imagen", "motivo": f"solo {len(refs)} fotos disponibles"}
            guardar_cache(cache)
            stats["sin_fotos_suficientes"] += 1
            time.sleep(0.3)
            continue

        print(f"         {len(refs)} fotos disponibles — probando {len(candidatas)} candidatas")

        encontrada = False
        for j, ref in enumerate(candidatas):
            idx_real = FOTO_INICIO + j
            print(f"         Foto índice {idx_real}...")

            data = descargar_foto_places(ref)
            if not data:
                continue

            archivo.parent.mkdir(parents=True, exist_ok=True)
            guardar_imagen(data, archivo)

            resultado = verificar_con_groq(archivo)
            time.sleep(0.5)

            if resultado is None:
                archivo.unlink(missing_ok=True)
                continue

            tiene_personas = resultado.get("tiene_personas", False)
            print(
                f"         Groq: es_iglesia={resultado['es_iglesia']} "
                f"tiene_personas={tiene_personas} "
                f"({resultado['confianza']}) — {resultado['descripcion']}"
            )

            if resultado["es_iglesia"] and not tiene_personas:
                nueva_url = (
                    f"https://maps.googleapis.com/maps/api/place/photo"
                    f"?maxwidth=800&photo_reference={ref}&key={GOOGLE_PLACES_API_KEY}"
                )
                Parroquia.objects.filter(pk=p.pk).update(imagen_url=nueva_url)
                cache[cache_key] = {
                    "resultado": "ok_segunda_pasada",
                    "descripcion": resultado["descripcion"],
                    "foto_index": idx_real,
                }
                guardar_cache(cache)
                stats["ok"] += 1
                encontrada = True
                print(f"         OK con foto índice {idx_real}")
                break
            else:
                motivo = resultado.get("motivo_rechazo") or (
                    "personas visibles" if tiene_personas else "no es iglesia"
                )
                print(f"         Rechazada: {motivo}")
                archivo.rename(CARPETA_RECHAZADAS / f"2da_{idx_real}_{archivo.name}")

        if not encontrada:
            cache[cache_key] = {"resultado": "segunda_pasada_sin_imagen", "motivo": "todas rechazadas"}
            guardar_cache(cache)
            stats["todas_rechazadas"] += 1
            print(f"         Sin imagen válida en esta pasada")

        time.sleep(4)

    guardar_cache(cache)

    print(f"\n━━━ RESUMEN SEGUNDA PASADA ━━━")
    print(f"Encontradas           : {stats['ok']}")
    print(f"Sin fotos suficientes : {stats['sin_fotos_suficientes']}")
    print(f"Todas rechazadas      : {stats['todas_rechazadas']}")
    print(f"Total procesadas      : {total}")


if __name__ == "__main__":
    main()
