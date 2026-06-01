import os, django, time, json
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
with open(".env", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()

django.setup()

from apps.iglesias.models import Parroquia
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

EXCLUIR = [
    "baiglesias",
    "barriada.com",
    "parroquiadelcarmenvcp",
    "google.com",
    "facebook.com",
    "instagram.com",
    "wikipedia",
    "tripadvisor",
    "horariosmisa",
    "horariodemisas",
    "buenosaires.gob.ar",
    "arzbaires.org.ar",
    "youtube.com",
    "tiktok.com",
    "twitter.com",
    "maps.google",
]

CACHE_FILE = "webs_cache.json"
BUSQUEDAS_FILE = "webs_busquedas.json"


def cargar_cache():
    if Path(CACHE_FILE).exists():
        with open(CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def guardar_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def cargar_busquedas():
    if Path(BUSQUEDAS_FILE).exists():
        with open(BUSQUEDAS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def guardar_busquedas(b):
    with open(BUSQUEDAS_FILE, "w", encoding="utf-8") as f:
        json.dump(b, f, ensure_ascii=False, indent=2)


def buscar_web(nombre, barrio):
    from scrapling.fetchers import DynamicFetcher
    from urllib.parse import quote, unquote

    query = f"{nombre} parroquia {barrio} Buenos Aires sitio oficial"
    url_busqueda = f"https://www.google.com/search?q={quote(query)}&num=5&hl=es"

    try:
        fetcher = DynamicFetcher()
        page = fetcher.fetch(
            url_busqueda,
            headless=True,
            wait=3000,
            network_idle=True,
        )

        resultados = []
        for a in page.find_all("a"):
            href = a.attrib.get("href", "")
            if "/url?q=" in href:
                href = href.split("/url?q=")[1].split("&")[0]
                href = unquote(href)
            if (
                href.startswith("http")
                and "google" not in href
                and not any(ex in href.lower() for ex in EXCLUIR)
            ):
                if href not in resultados:
                    resultados.append(href)
                    if len(resultados) >= 4:
                        break

        print(f"  Resultados: {resultados}")
        return resultados

    except Exception as e:
        print(f"  ERROR: {e}")
        return []


parroquias = list(
    Parroquia.objects.filter(sitio_web__isnull=True)
    .exclude(nombre__icontains="TEST")
    .order_by("nombre")
    .values("pk", "nombre", "barrio", "direccion")
)

HTML_FILE = Path("panel.html").read_text(encoding="utf-8")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_FILE.encode())

        elif self.path == "/api/parroquias":
            cache_actual = cargar_cache()
            busquedas = cargar_busquedas()
            data = []
            for p in parroquias:
                data.append({**p, "resultados": busquedas.get(str(p["pk"]), [])})
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(
                json.dumps(
                    {"parroquias": data, "cache": cache_actual}, ensure_ascii=False
                ).encode()
            )

        elif self.path == "/api/buscar-todas":

            def buscar_todas():
                busquedas = cargar_busquedas()
                cache_actual = cargar_cache()
                pendientes = [
                    p
                    for p in parroquias
                    if str(p["pk"]) not in cache_actual
                    and str(p["pk"]) not in busquedas
                ]
                print(f"Búsqueda masiva: {len(pendientes)} parroquias pendientes...")
                for p in pendientes:
                    res = buscar_web(p["nombre"].title(), p["barrio"] or "")
                    busquedas[str(p["pk"])] = res
                    if res:
                        print(f"  ✓ {p['nombre'][:40]} → {res[0]}")
                    else:
                        print(f"  ✗ {p['nombre'][:40]} — sin resultado")
                    guardar_busquedas(busquedas)
                    time.sleep(2)
                print("Búsqueda masiva completada.")

            threading.Thread(target=buscar_todas, daemon=True).start()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok": true}')

        elif self.path.startswith("/api/buscar/"):
            pk = int(self.path.split("/")[-1])
            p = next((x for x in parroquias if x["pk"] == pk), None)
            resultados = []
            if p:
                resultados = buscar_web(p["nombre"].title(), p["barrio"] or "")
                busquedas = cargar_busquedas()
                busquedas[str(pk)] = resultados
                guardar_busquedas(busquedas)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"resultados": resultados}).encode())

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        cache_actual = cargar_cache()

        if self.path == "/api/aplicar":
            pk = body["pk"]
            url = body["url"]
            try:
                p = Parroquia.objects.get(pk=pk)
                p.sitio_web = url
                p.save(update_fields=["sitio_web"])
                cache_actual[str(pk)] = url
                guardar_cache(cache_actual)
                print(f"  ✓ {p.nombre[:40]} → {url}")
            except Exception as e:
                print(f"  ERROR pk={pk}: {e}")

        elif self.path == "/api/omitir":
            pk = str(body["pk"])
            cache_actual[pk] = "SKIP"
            guardar_cache(cache_actual)

        elif self.path == "/api/deshacer":
            pk = str(body["pk"])
            if pk in cache_actual:
                del cache_actual[pk]
                guardar_cache(cache_actual)
            try:
                p = Parroquia.objects.get(pk=int(pk))
                p.sitio_web = None
                p.save(update_fields=["sitio_web"])
            except Exception:
                pass

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok": true}')


if __name__ == "__main__":
    server = HTTPServer(("localhost", 8765), Handler)
    print(f"Panel disponible en: http://localhost:8765")
    print(f"Parroquias sin web: {len(parroquias)}")
    print(f"Usá el botón 'Buscar todas' en el panel para iniciar la búsqueda masiva.")
    server.serve_forever()
