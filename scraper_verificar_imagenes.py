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

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
GOOGLE_PLACES_API_KEY = os.environ["GOOGLE_PLACES_API_KEY"]
CARPETA_BASE = Path("imagenes_parroquias")
CARPETA_RECHAZADAS = Path("imagenes_rechazadas")
CARPETA_RECHAZADAS.mkdir(exist_ok=True)
CACHE_FILE = Path("verificacion_cache.json")

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ParroGuia-bot/1.0)"}


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
    return CARPETA_BASE / prov


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


import groq  # pip install groq

GROQ_API_KEY = os.environ["GROQ_API_KEY"]
groq_client = groq.Groq(api_key=GROQ_API_KEY)


def verificar_con_groq(imagen_path, reintentos=3):
    try:
        img = Image.open(imagen_path).convert("RGB")
        # Redimensionar si es muy grande (Groq tiene límite de tamaño)
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

            except groq.RateLimitError as e:
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


def buscar_fotos_alternativas(parroquia):
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
    except:
        return None


def guardar_imagen(data, archivo):
    img = Image.open(BytesIO(data)).convert("RGB")
    img.save(archivo, "JPEG", quality=85, optimize=True)


def main():
    cache = cargar_cache()

    parroquias = Parroquia.objects.exclude(imagen_url="").order_by("provincia", "pk")
    total = parroquias.count()

    print(f"\nParroquias a verificar: {total}")
    print(f"Cache existente: {len(cache)} entradas\n")

    stats = {
        "ok_primera": 0,
        "ok_alternativa": 0,
        "rechazada_sin_alternativa": 0,
        "sin_archivo": 0,
        "error_gemini": 0,
        "ya_verificada": 0,
    }

    for i, p in enumerate(parroquias, 1):
        cache_key = str(p.pk)

        if cache_key in cache and cache[cache_key].get("resultado") == "ok":
            stats["ya_verificada"] += 1
            continue

        carpeta = subcarpeta(p)
        archivo = carpeta / nombre_archivo(p)

        if not archivo.exists():
            print(f"[{i}/{total}] SIN ARCHIVO: {p.nombre}")
            stats["sin_archivo"] += 1
            continue

        print(f"[{i}/{total}] {p.nombre} | {p.ciudad or p.barrio or ''}")

        resultado = verificar_con_groq(archivo)

        if resultado is None:
            stats["error_gemini"] += 1
            time.sleep(2)
            continue

        tiene_personas = resultado.get("tiene_personas", False)
        print(
            f"         Groq: es_iglesia={resultado['es_iglesia']} "
            f"tiene_personas={tiene_personas} "
            f"({resultado['confianza']}) — {resultado['descripcion']}"
        )

        if resultado["es_iglesia"] and not tiene_personas:
            cache[cache_key] = {
                "resultado": "ok",
                "descripcion": resultado["descripcion"],
            }
            guardar_cache(cache)
            stats["ok_primera"] += 1
            time.sleep(4)
            continue

        motivo = resultado.get("motivo_rechazo") or ("personas visibles en la foto" if tiene_personas else "no es iglesia")
        print(f"         RECHAZADA: {motivo}")

        rechazada_dest = CARPETA_RECHAZADAS / archivo.name
        archivo.rename(rechazada_dest)

        photo_references = buscar_fotos_alternativas(p)
        photo_references = photo_references[1:] if len(photo_references) > 1 else []

        encontrada = False
        for j, ref in enumerate(photo_references[:4]):
            print(
                f"         Probando foto alternativa {j+1}/{min(len(photo_references), 4)}..."
            )
            data = descargar_foto_places(ref)
            if not data:
                continue

            archivo.parent.mkdir(parents=True, exist_ok=True)
            guardar_imagen(data, archivo)

            resultado_alt = verificar_con_groq(archivo)
            time.sleep(0.5)

            if resultado_alt is None:
                continue

            tiene_personas_alt = resultado_alt.get("tiene_personas", False)
            print(
                f"         Alternativa: es_iglesia={resultado_alt['es_iglesia']} "
                f"tiene_personas={tiene_personas_alt} "
                f"— {resultado_alt['descripcion']}"
            )

            if resultado_alt["es_iglesia"] and not tiene_personas_alt:
                nueva_url = (
                    f"https://maps.googleapis.com/maps/api/place/photo"
                    f"?maxwidth=800&photo_reference={ref}&key={GOOGLE_PLACES_API_KEY}"
                )
                Parroquia.objects.filter(pk=p.pk).update(imagen_url=nueva_url)
                cache[cache_key] = {
                    "resultado": "ok_alternativa",
                    "descripcion": resultado_alt["descripcion"],
                    "foto_index": j + 1,
                }
                guardar_cache(cache)
                stats["ok_alternativa"] += 1
                encontrada = True
                print(f"         OK con foto alternativa {j+1}")
                break
            else:
                archivo.rename(CARPETA_RECHAZADAS / f"alt{j+1}_{archivo.name}")

        if not encontrada:
            Parroquia.objects.filter(pk=p.pk).update(imagen_url="")
            cache[cache_key] = {"resultado": "sin_imagen_valida"}
            guardar_cache(cache)
            stats["rechazada_sin_alternativa"] += 1
            print(f"         Sin imagen válida — imagen_url limpiada")

        time.sleep(4)

    guardar_cache(cache)

    print(f"\n━━━ RESUMEN ━━━")
    print(f"OK (primera foto)       : {stats['ok_primera']}")
    print(f"OK (foto alternativa)   : {stats['ok_alternativa']}")
    print(f"Sin imagen válida       : {stats['rechazada_sin_alternativa']}")
    print(f"Sin archivo en disco    : {stats['sin_archivo']}")
    print(f"Errores Gemini          : {stats['error_gemini']}")
    print(f"Ya verificadas (cache)  : {stats['ya_verificada']}")
    print(f"\nImágenes rechazadas guardadas en: {CARPETA_RECHAZADAS.resolve()}")
    print(f"Cache guardado en: {CACHE_FILE.resolve()}")


if __name__ == "__main__":
    main()
