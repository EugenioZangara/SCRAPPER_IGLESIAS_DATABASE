import sys
import os
import time
import random
import json
from urllib.parse import urlparse

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django

django.setup()

import httpx
from bs4 import BeautifulSoup
from apps.iglesias.models import Parroquia

EXCLUIR = [
    "baiglesias.com",
    "buenosaires.gob.ar",
    "turismo.buenosaires.gob.ar",
    "es.wikipedia.org",
    "en.wikipedia.org",
    "wanderlog.com",
    "linktr.ee",
    "fatima.pt",
    "czestochowa.us",
    "catholicapostolatecenterfeastdays.org",
    "queenofapostles.org",
    "parroquiadelcarmenvcp.com.ar",
]

KEYWORDS_UTILES = [
    "horario",
    "misa",
    "misas",
    "sacramento",
    "sacramentos",
    "bautismo",
    "matrimonio",
    "confesion",
    "confesión",
    "secretaria",
    "secretaría",
    "contacto",
    "dirección",
    "direccion",
    "actividades",
    "agenda",
    "eventos",
    "retiro",
    "catequesis",
]

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ParroquiaScraper/1.0)"}


def detectar_tecnologia(html: str, headers: dict) -> str:
    """Detecta el CMS o tecnología del sitio."""
    html_lower = html.lower()
    server = headers.get("server", "").lower()
    x_powered = headers.get("x-powered-by", "").lower()

    if "wp-content" in html_lower or "wordpress" in html_lower:
        return "wordpress"
    if "wixsite" in html_lower or "wix.com" in html_lower:
        return "wix"
    if "blogger" in html_lower or "blogspot" in html_lower:
        return "blogger"
    if "sites.google.com" in html_lower:
        return "google-sites"
    if "weebly" in html_lower:
        return "weebly"
    if "squarespace" in html_lower:
        return "squarespace"
    if "joomla" in html_lower:
        return "joomla"
    if "drupal" in html_lower:
        return "drupal"
    return "custom"


def analizar_url(parroquia) -> dict:
    """Visita la URL de la parroquia y analiza su contenido."""
    url = parroquia.sitio_web
    resultado = {
        "id": parroquia.id,
        "nombre": parroquia.nombre,
        "url": url,
        "status": None,
        "tecnologia": None,
        "keywords_encontradas": [],
        "tiene_contenido_util": False,
        "titulo_pagina": None,
        "error": None,
    }

    try:
        response = httpx.get(url, timeout=12, follow_redirects=True, headers=HEADERS)
        resultado["status"] = response.status_code
        resultado["url_final"] = str(response.url)

        if response.status_code != 200:
            return resultado

        html = response.text
        soup = BeautifulSoup(html, "html.parser")

        # Título
        title_tag = soup.find("title")
        if title_tag:
            resultado["titulo_pagina"] = title_tag.get_text().strip()[:80]

        # Tecnología
        resultado["tecnologia"] = detectar_tecnologia(html, dict(response.headers))

        # Keywords útiles
        texto = soup.get_text().lower()
        encontradas = [kw for kw in KEYWORDS_UTILES if kw in texto]
        resultado["keywords_encontradas"] = encontradas
        resultado["tiene_contenido_util"] = len(encontradas) >= 3

    except httpx.TimeoutException:
        resultado["error"] = "timeout"
    except httpx.ConnectError:
        resultado["error"] = "connection_error"
    except Exception as e:
        resultado["error"] = str(e)[:80]

    return resultado


def main():
    parroquias = Parroquia.objects.exclude(sitio_web__isnull=True).exclude(sitio_web="")

    candidatas = []
    for p in parroquias:
        try:
            dominio = urlparse(p.sitio_web).netloc.replace("www.", "")
            if not any(ex in dominio for ex in EXCLUIR):
                candidatas.append(p)
        except:
            pass

    total = len(candidatas)
    print(f"=== Reconocimiento web ===")
    print(f"Parroquias a analizar: {total}\n")

    resultados = []
    errores = 0
    utiles = 0

    for i, parroquia in enumerate(candidatas, 1):
        print(f"[{i:3}/{total}] {parroquia.nombre[:45]:45}", end=" → ")
        resultado = analizar_url(parroquia)
        resultados.append(resultado)

        if resultado["error"]:
            print(f"❌ {resultado['error']}")
            errores += 1
        elif resultado["status"] != 200:
            print(f"⚠️  HTTP {resultado['status']}")
        elif resultado["tiene_contenido_util"]:
            kws = ", ".join(resultado["keywords_encontradas"][:4])
            print(f"✅ {resultado['tecnologia']:12} [{kws}]")
            utiles += 1
        else:
            kws = ", ".join(resultado["keywords_encontradas"][:3]) or "ninguna"
            print(f"〰️  {resultado['tecnologia']:12} [{kws}]")

        if i < total:
            time.sleep(random.uniform(1.5, 3.5))

    # Guardar resultados
    output_path = "reconocimiento_web_resultados.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)

    # Resumen
    print(f"\n=== RESUMEN ===")
    print(f"Total analizadas  : {total}")
    print(f"Con contenido útil: {utiles}")
    print(f"Errores/timeout   : {errores}")
    print(f"Resultados en     : {output_path}")

    # Agrupar por tecnología
    from collections import Counter

    tecno = Counter(
        r["tecnologia"] for r in resultados if r["tecnologia"] and not r["error"]
    )
    print(f"\nPor tecnología:")
    for t, n in tecno.most_common():
        print(f"  {n:3}x  {t}")

    # Top sitios útiles
    utiles_lista = [
        r for r in resultados if r["tiene_contenido_util"] and not r["error"]
    ]
    print(f"\nSitios con más contenido útil ({len(utiles_lista)}):")
    for r in sorted(utiles_lista, key=lambda x: -len(x["keywords_encontradas"]))[:15]:
        kws = len(r["keywords_encontradas"])
        print(f"  {kws} keywords — {r['nombre'][:40]:40} {r['tecnologia']}")


main()
