import os, django, httpx, time, re
from bs4 import BeautifulSoup
from difflib import SequenceMatcher

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
with open(".env", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()
django.setup()

from apps.iglesias.models import Parroquia

BASE_URL = "https://horariosmisa.com.ar/ciudad-autonoma-de-buenos-aires/buenos-aires/"


def similaridad(a, b):
    a = re.sub(r"[^\w\s]", "", a.lower())
    b = re.sub(r"[^\w\s]", "", b.lower())
    return SequenceMatcher(None, a, b).ratio()


def buscar_match(nombre, parroquias):
    mejor, score = None, 0
    for p in parroquias:
        s = similaridad(nombre, p.nombre)
        if s > score:
            score = s
            mejor = p
    return mejor, score


parroquias_db = list(Parroquia.objects.all())
resp = httpx.get(BASE_URL, timeout=15, headers={"User-Agent": "ParroGuia/1.0"})
from bs4 import BeautifulSoup

soup = BeautifulSoup(resp.text, "html.parser")
urls = [
    a["href"]
    for a in soup.find_all("a", href=True)
    if a["href"].startswith(BASE_URL) and a["href"] != BASE_URL
]

print(f"Analizando {len(set(urls))} parroquias...\n")

for url in set(urls):
    try:
        r = httpx.get(url, timeout=15, headers={"User-Agent": "ParroGuia/1.0"})
        s = BeautifulSoup(r.text, "html.parser")
        h1 = s.find("h1")
        if not h1:
            continue
        nombre = re.sub(
            r"\s*-\s*Buenos Aires.*$", "", h1.get_text(strip=True), flags=re.IGNORECASE
        )
        p, score = buscar_match(nombre, parroquias_db)
        if score < 0.55:
            print(f"SIN MATCH ({score:.2f}): '{nombre}'")
            print(f"  Más cercano: '{p.nombre}'")
        time.sleep(0.5)
    except Exception as e:
        print(f"ERROR: {e}")
