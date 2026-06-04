import os, django, httpx, time, re, json
from bs4 import BeautifulSoup
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
with open(".env", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()
django.setup()

from apps.iglesias.models import Parroquia, HorarioMisa

BASE = "https://horariosmisa.com.ar"
HEADERS = {"User-Agent": "ParroGuia/1.0 scraper@parroguia.com.ar"}

DIAS_MAP = {
    "lunes": 0,
    "martes": 1,
    "miércoles": 2,
    "miercoles": 2,
    "jueves": 3,
    "viernes": 4,
    "sábado": 5,
    "sabado": 5,
    "domingo": 6,
}

# Provincias a scrapear (excluir CABA que ya está)
PROVINCIAS = [
    ("https://horariosmisa.com.ar/provincia-de-buenos-aires/", "Buenos Aires"),
    ("https://horariosmisa.com.ar/provincia-de-cordoba/", "Córdoba"),
    ("https://horariosmisa.com.ar/santa-fe/", "Santa Fe"),
    ("https://horariosmisa.com.ar/provincia-de-mendoza/", "Mendoza"),
    ("https://horariosmisa.com.ar/provincia-de-salta/", "Salta"),
    ("https://horariosmisa.com.ar/misiones/", "Misiones"),
    ("https://horariosmisa.com.ar/entre-rios/", "Entre Ríos"),
    ("https://horariosmisa.com.ar/chaco/", "Chaco"),
    ("https://horariosmisa.com.ar/jujuy/", "Jujuy"),
    ("https://horariosmisa.com.ar/rio-negro/", "Río Negro"),
    ("https://horariosmisa.com.ar/provincia-de-neuquen/", "Neuquén"),
    ("https://horariosmisa.com.ar/chubut/", "Chubut"),
    ("https://horariosmisa.com.ar/provincia-de-corrientes/", "Corrientes"),
    ("https://horariosmisa.com.ar/catamarca/", "Catamarca"),
    ("https://horariosmisa.com.ar/la-pampa/", "La Pampa"),
    ("https://horariosmisa.com.ar/provincia-de-san-juan/", "San Juan"),
    ("https://horariosmisa.com.ar/provincia-de-san-luis/", "San Luis"),
    ("https://horariosmisa.com.ar/provincia-de-formosa/", "Formosa"),
    ("https://horariosmisa.com.ar/provincia-de-la-rioja/", "La Rioja"),
    (
        "https://horariosmisa.com.ar/provincia-de-santiago-del-estero/",
        "Santiago del Estero",
    ),
]

# Cache para no repetir requests
CACHE_FILE = "scraper_nacional_cache.json"


def cargar_cache():
    if Path(CACHE_FILE).exists():
        with open(CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def guardar_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def fetch(url):
    try:
        resp = httpx.get(url, timeout=15, headers=HEADERS, follow_redirects=True)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        print(f"  ERROR fetch {url}: {e}")
        return None


def obtener_ciudades(url_provincia):
    soup = fetch(url_provincia)
    if not soup:
        return []
    ciudades = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if (
            href.startswith(url_provincia)
            and href != url_provincia
            and href.count("/") == 5
        ):
            ciudades.append(href.rstrip("/") + "/")
    return list(set(ciudades))


def obtener_urls_parroquias(url_ciudad):
    soup = fetch(url_ciudad)
    if not soup:
        return []
    urls = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith(url_ciudad) and href != url_ciudad and href.count("/") == 6:
            urls.append(href.rstrip("/") + "/")
    return list(set(urls))


def scrapear_parroquia(url):
    soup = fetch(url)
    if not soup:
        return None

    # Nombre
    h1 = soup.find("h1")
    if not h1:
        return None
    nombre = re.sub(r"\s*-\s*.+$", "", h1.get_text(strip=True), flags=re.IGNORECASE)
    nombre = nombre.strip()

    # Datos de contacto
    direccion = ""
    telefono = ""
    sitio_web = ""

    for item in soup.find_all(["p", "div", "span"]):
        texto = item.get_text(strip=True)
        if "Dirección:" in texto or "Calle:" in texto:
            direccion = texto.replace("Dirección:", "").replace("Calle:", "").strip()
        if "Teléfono:" in texto:
            telefono = texto.replace("Teléfono:", "").strip()
        if "Sitio web:" in texto or "Web:" in texto:
            a = item.find("a", href=True)
            if a:
                sitio_web = a["href"]

    # Horarios
    horarios = {}
    tabla = soup.find("table")
    if tabla:
        for row in tabla.find_all("tr"):
            celdas = row.find_all(["td", "th"])
            if len(celdas) >= 2:
                dia_texto = celdas[0].get_text(strip=True).lower()
                horario_texto = celdas[1].get_text(strip=True)
                dia_num = DIAS_MAP.get(dia_texto)
                if dia_num is not None and horario_texto:
                    horas = [h.strip() for h in horario_texto.split(",")]
                    horarios[dia_num] = " · ".join(horas)

    return {
        "nombre": nombre,
        "direccion": direccion,
        "telefono": telefono,
        "sitio_web": sitio_web,
        "horarios": horarios,
        "url": url,
    }


def crear_parroquia(datos, ciudad, provincia):
    nombre = datos["nombre"].upper()

    # Verificar si ya existe
    existente = Parroquia.objects.filter(
        nombre__iexact=nombre, ciudad__iexact=ciudad, provincia__iexact=provincia
    ).first()

    if existente:
        return existente, False

    # ID externo basado en hash de URL
    

    import hashlib
    hash_hex = hashlib.md5(datos['url'].encode()).hexdigest()[:7]
    id_externo = int(hash_hex, 16) % 2000000000  # max ~2B

    # Evitar colisión de id_externo
    while Parroquia.objects.filter(id_externo=id_externo).exists():
        id_externo += 1

    p = Parroquia.objects.create(
        id_externo=id_externo,
        nombre=nombre,
        url_detalle=datos["url"],
        direccion=datos["direccion"] or None,
        telefonos=datos["telefono"] or None,
        sitio_web=datos["sitio_web"] or None,
        ciudad=ciudad,
        provincia=provincia,
        barrio=ciudad,
    )

    # Crear horarios
    for dia, horario in datos["horarios"].items():
        HorarioMisa.objects.get_or_create(
            parroquia=p,
            dia_semana=dia,
            defaults={"horarios": horario, "fuente": "scraper_web"},
        )

    return p, True


def main():
    cache = cargar_cache()
    total_creadas = 0
    total_existentes = 0
    total_errores = 0

    for url_provincia, nombre_provincia in PROVINCIAS:
        print(f"\n{'='*50}")
        print(f"PROVINCIA: {nombre_provincia}")
        print(f"{'='*50}")

        if url_provincia in cache.get("provincias_completadas", []):
            print(f"  Ya procesada — saltando")
            continue

        ciudades = obtener_ciudades(url_provincia)
        print(f"  {len(ciudades)} ciudades encontradas")
        time.sleep(1)

        for url_ciudad in ciudades:
            ciudad = url_ciudad.rstrip("/").split("/")[-1].replace("-", " ").title()
            print(f"\n  Ciudad: {ciudad}")

            urls_parroquias = obtener_urls_parroquias(url_ciudad)
            print(f"    {len(urls_parroquias)} parroquias")
            time.sleep(0.8)

            for url_parroquia in urls_parroquias:
                if url_parroquia in cache.get("urls_procesadas", []):
                    total_existentes += 1
                    continue

                try:
                    datos = scrapear_parroquia(url_parroquia)
                    if not datos or not datos["nombre"]:
                        total_errores += 1
                        continue

                    parroquia, creada = crear_parroquia(datos, ciudad, nombre_provincia)

                    if creada:
                        total_creadas += 1
                        print(f"    ✓ {parroquia.nombre[:50]}")
                    else:
                        total_existentes += 1

                    # Guardar en cache
                    if "urls_procesadas" not in cache:
                        cache["urls_procesadas"] = []
                    cache["urls_procesadas"].append(url_parroquia)
                    guardar_cache(cache)

                    time.sleep(0.8)

                except Exception as e:
                    print(f"    ERROR {url_parroquia}: {e}")
                    total_errores += 1
                    time.sleep(1)

        # Marcar provincia como completada
        if "provincias_completadas" not in cache:
            cache["provincias_completadas"] = []
        cache["provincias_completadas"].append(url_provincia)
        guardar_cache(cache)

    print(f"\n{'='*50}")
    print(f"RESUMEN FINAL")
    print(f"{'='*50}")
    print(f"Creadas   : {total_creadas}")
    print(f"Existentes: {total_existentes}")
    print(f"Errores   : {total_errores}")


if __name__ == "__main__":
    main()
