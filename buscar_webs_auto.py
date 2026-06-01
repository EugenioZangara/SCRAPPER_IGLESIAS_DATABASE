import os, django, httpx, time, json
from urllib.parse import quote

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
with open(".env", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()
django.setup()

from apps.iglesias.models import Parroquia

# Dominios a excluir — no son webs propias de parroquias
EXCLUIR = [
    "baiglesias",
    "barriada.com",
    "parroquiadelcarmenvcp",
    "google.com",
    "facebook.com",
    "instagram.com",
    "wikipedia",
    "tripadvisor",
    "yelp",
    "horariosmisa",
    "buenosaires.gob.ar",
    "arzbaires.org.ar",
    "youtube.com",
    "tiktok.com",
    "twitter.com",
]


def buscar_duckduckgo(query):
    """Busca en DuckDuckGo y retorna el primer resultado relevante."""
    try:
        resp = httpx.get(
            "https://api.duckduckgo.com/",
            params={
                "q": query,
                "format": "json",
                "no_redirect": "1",
                "no_html": "1",
            },
            timeout=10,
            headers={"User-Agent": "ParroGuia/1.0"},
        )
        data = resp.json()

        # Buscar en resultados relacionados
        for r in data.get("RelatedTopics", []):
            url = r.get("FirstURL", "")
            if url and not any(ex in url for ex in EXCLUIR):
                return url

        return None
    except Exception as e:
        print(f"  ERROR DuckDuckGo: {e}")
        return None


def buscar_google_scrape(parroquia_nombre, barrio):
    """Alternativa: buscar via httpx directo."""
    query = f"{parroquia_nombre} parroquia {barrio} Buenos Aires sitio oficial"
    try:
        resp = httpx.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            timeout=15,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept-Language": "es-AR,es;q=0.9",
            },
        )
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(resp.text, "html.parser")

        for result in soup.find_all("a", class_="result__url"):
            url = result.get("href", "")
            text = result.get_text(strip=True)
            if url and not any(ex in url.lower() for ex in EXCLUIR):
                if not url.startswith("http"):
                    url = "https://" + url
                return url, text

        return None, None
    except Exception as e:
        print(f"  ERROR búsqueda: {e}")
        return None, None


sin_web = (
    Parroquia.objects.filter(sitio_web__isnull=True)
    .exclude(nombre__icontains="TEST")
    .order_by("nombre")
)

print(f"Buscando webs para {sin_web.count()} parroquias...\n")

resultados = []

for i, p in enumerate(sin_web, 1):
    barrio = p.barrio or ""
    nombre_limpio = p.nombre.replace("(", "").replace(")", "").strip()
    query = f"{nombre_limpio} parroquia {barrio} Buenos Aires"

    print(f"[{i}/{sin_web.count()}] {p.nombre[:45]}")

    url, texto = buscar_google_scrape(nombre_limpio, barrio)

    if url:
        print(f"  ✓ {url}")
        resultados.append(
            {
                "pk": p.pk,
                "nombre": p.nombre,
                "barrio": barrio,
                "url_encontrada": url,
            }
        )
    else:
        print(f"  ✗ Sin resultado")
        resultados.append(
            {
                "pk": p.pk,
                "nombre": p.nombre,
                "barrio": barrio,
                "url_encontrada": None,
            }
        )

    time.sleep(1.5)  # respetar el servidor

# Guardar resultados para revisión
with open("webs_encontradas.json", "w", encoding="utf-8") as f:
    json.dump(resultados, f, ensure_ascii=False, indent=2)

encontradas = [r for r in resultados if r["url_encontrada"]]
print(f"\n=== RESUMEN ===")
print(f"Total        : {len(resultados)}")
print(f"Con URL      : {len(encontradas)}")
print(f"Sin resultado: {len(resultados) - len(encontradas)}")
print(f"\nResultados guardados en webs_encontradas.json")
print(f"Revisá el archivo y luego corré: python aplicar_webs.py")
