import json
import httpx
from bs4 import BeautifulSoup
import time
import random

with open("reconocimiento_web_resultados.json", encoding="utf-8") as f:
    data = json.load(f)

# Solo WordPress con contenido útil
wp_sites = [
    r
    for r in data
    if r.get("tecnologia") == "wordpress"
    and r.get("status") == 200
    and not r.get("error")
]

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ParroquiaScraper/1.0)"}

# Patrones de URLs que suelen tener eventos/cartelera en WordPress
PATRONES_EVENTOS = [
    "/eventos/",
    "/evento/",
    "/agenda/",
    "/cartelera/",
    "/novedades/",
    "/noticias/",
    "/actividades/",
    "/news/",
    "/category/eventos/",
    "/category/agenda/",
]


def buscar_links_eventos(url_base: str, html: str) -> list:
    """Busca links en el menú que sugieran sección de eventos."""
    soup = BeautifulSoup(html, "html.parser")
    links_encontrados = []

    # Buscar en navegación
    nav_links = soup.find_all("a", href=True)
    for link in nav_links:
        href = link.get("href", "").lower()
        texto = link.get_text().lower().strip()
        palabras_clave = [
            "evento",
            "agenda",
            "cartelera",
            "novedad",
            "noticia",
            "actividad",
            "aviso",
            "anuncio",
        ]
        if any(p in href or p in texto for p in palabras_clave):
            full_url = (
                href
                if href.startswith("http")
                else url_base.rstrip("/") + "/" + href.lstrip("/")
            )
            if url_base.split("/")[2] in full_url:  # mismo dominio
                links_encontrados.append(
                    {"texto": link.get_text().strip()[:30], "url": full_url[:100]}
                )

    # Deduplicar
    seen = set()
    unique = []
    for l in links_encontrados:
        if l["url"] not in seen:
            seen.add(l["url"])
            unique.append(l)

    return unique[:5]


print(f"Analizando {len(wp_sites)} sitios WordPress...\n")
print(f"{'PARROQUIA':45} LINKS DE EVENTOS ENCONTRADOS")
print("-" * 100)

con_seccion_eventos = []

for r in wp_sites:
    url = r["url"]
    try:
        response = httpx.get(url, timeout=10, follow_redirects=True, headers=HEADERS)
        if response.status_code != 200:
            print(f"  {r['nombre'][:43]:45} HTTP {response.status_code}")
            continue

        links = buscar_links_eventos(url, response.text)

        if links:
            con_seccion_eventos.append(
                {"nombre": r["nombre"], "url": url, "links": links}
            )
            links_str = " | ".join(
                [f"{l['texto']} → {l['url'][:50]}" for l in links[:2]]
            )
            print(f"  ✅ {r['nombre'][:43]:45} {links_str}")
        else:
            print(f"  〰️  {r['nombre'][:43]:45} sin sección de eventos")

    except Exception as e:
        print(f"  ❌ {r['nombre'][:43]:45} {str(e)[:40]}")

    time.sleep(random.uniform(1, 2.5))

print(f"\n=== RESUMEN ===")
print(f"WordPress con sección de eventos: {len(con_seccion_eventos)}/{len(wp_sites)}")
print(f"\nDetalle:")
for s in con_seccion_eventos:
    print(f"\n  {s['nombre']}")
    for l in s["links"]:
        print(f"    → {l['texto']:25} {l['url']}")
