import os
import re
import time
import unicodedata
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from apps.iglesias.models import Parroquia, RedSocial

from .config import HEADERS, validar_web

SERPER_API_KEY = os.environ.get("SERPER_API_KEY")

TIMEOUT_RED_SOCIAL = 10

SOCIAL_DOMAINS = {
    "facebook.com": "facebook",
    "fb.com": "facebook",
    "instagram.com": "instagram",
    "youtube.com": "youtube",
    "youtu.be": "youtube",
    "tiktok.com": "tiktok",
    "twitter.com": "otro",
    "x.com": "otro",
}

EXCLUDED_PATH_PARTS = {
    "facebook": (
        "/plugins/",
        "/sharer/",
        "/sharer.php",
        "/share.php",
        "/dialog/",
        "/login",
        "/privacy",
        "/terms",
        "/tr/",
        "/events/",
    ),
    "instagram": (
        "/accounts/",
        "/oauth/",
        "/p/",
        "/reel/",
        "/reels/",
        "/stories/",
        "/explore/",
        "/privacy",
        "/terms",
    ),
    "youtube": (
        "/embed/",
        "/watch",
        "/playlist",
        "/results",
        "/redirect",
        "/shorts/",
        "/privacy",
        "/terms",
    ),
    "tiktok": (
        "/embed/",
        "/share/",
        "/login",
        "/tag/",
        "/music/",
        "/video/",
        "/privacy",
        "/terms",
    ),
    "otro": (
        "/intent/",
        "/share",
        "/login",
        "/i/",
        "/home",
        "/search",
        "/hashtag/",
        "/privacy",
        "/terms",
    ),
}

IGNORED_QUERY_PARAMS = {
    "fbclid",
    "igshid",
    "utm_campaign",
    "utm_content",
    "utm_medium",
    "utm_source",
    "utm_term",
}

TERMINOS_GENERICOS_NO_OFICIALES = {
    "baiglesias",
    "gcba",
    "buenosaires",
    "buenos aires",
    "gobierno",
    "ciudad",
}

PALABRAS_NO_SIGNIFICATIVAS = {
    "de",
    "del",
    "la",
    "las",
    "los",
    "el",
    "y",
    "san",
    "santa",
    "santo",
    "santisima",
    "nuestra",
    "senor",
    "senora",
    "parroquia",
}

DOMINIOS_ARGENTINA = {
    ".ar",
}

DOMINIOS_EXTRANJEROS_RIESGOSOS = {
    ".br",
    ".cl",
    ".co",
    ".es",
    ".it",
    ".mx",
    ".pe",
    ".pl",
    ".uy",
}

TERMINOS_ARGENTINA = {
    "argentina",
    "buenos aires",
    "caba",
    "ciudad autonoma",
    "capital federal",
    "arzbaires",
    "arquidiocesis de buenos aires",
    "arquidiocesis buenos aires",
}

TERMINOS_EXTRANJEROS_RIESGOSOS = {
    "brasil",
    "brazil",
    "chile",
    "colombia",
    "espana",
    "italia",
    "italy",
    "mexico",
    "peru",
    "poland",
    "polonia",
    "polska",
    "uruguay",
}

INDICIOS_ARGENTINA_EN_URL = {
    "argentina",
    "buenosaires",
    "buenos-aires",
    "caba",
    "arzbaires",
}


def buscar_web(nombre, barrio):
    if not SERPER_API_KEY:
        print("SERPER_API_KEY no configurada. Se omite busqueda externa.")
        return None

    query = f"{nombre} {barrio} parroquia Buenos Aires Argentina sitio oficial"

    try:
        response = requests.post(
            "https://google.serper.dev/search",
            headers={
                "X-API-KEY": SERPER_API_KEY,
                "Content-Type": "application/json",
            },
            json={"q": query, "gl": "ar", "hl": "es", "location": "Argentina"},
            timeout=TIMEOUT_RED_SOCIAL,
        )

        response.raise_for_status()
        data = response.json()

        for item in data.get("organic", []):
            link = item.get("link", "")
            texto_resultado = " ".join(
                [
                    item.get("title", ""),
                    item.get("snippet", ""),
                    link,
                ]
            )

            if any(
                x in link
                for x in ["facebook.com", "instagram.com", "youtube.com", "twitter.com"]
            ):
                continue

            if not resultado_parece_de_argentina(link, texto_resultado, barrio):
                print(f"Web omitida por no parecer de Argentina: {link}")
                continue

            if validar_web(link):
                return link

    except Exception as e:
        print(f"Error buscando web para {nombre}: {e}")

    return None


def dominio_tiene_sufijo(netloc, sufijos):
    dominio = netloc.lower()
    if dominio.startswith("www."):
        dominio = dominio[4:]

    return any(dominio.endswith(sufijo) for sufijo in sufijos)


def texto_tiene_indicios_argentina(texto, barrio=None):
    texto_normalizado = normalizar_texto_comparacion(texto)

    if not texto_normalizado:
        return False

    if any(termino in texto_normalizado for termino in TERMINOS_ARGENTINA):
        return True

    if barrio and normalizar_texto_comparacion(barrio) in texto_normalizado:
        return True

    return False


def texto_tiene_indicios_extranjeros(texto):
    texto_normalizado = normalizar_texto_comparacion(texto)

    if not texto_normalizado:
        return False

    return any(termino in texto_normalizado for termino in TERMINOS_EXTRANJEROS_RIESGOSOS)


def url_tiene_indicios_argentina(url):
    parsed = urlparse(normalizar_url_web(url) or "")
    netloc = parsed.netloc.lower()
    url_normalizada = normalizar_texto_comparacion(url)
    url_sin_espacios = url_normalizada.replace(" ", "")

    if dominio_tiene_sufijo(netloc, DOMINIOS_ARGENTINA):
        return True

    return any(indicio in url_sin_espacios for indicio in INDICIOS_ARGENTINA_EN_URL)


def url_tiene_dominio_extranjero_riesgoso(url):
    parsed = urlparse(normalizar_url_web(url) or "")
    netloc = parsed.netloc.lower()

    return dominio_tiene_sufijo(netloc, DOMINIOS_EXTRANJEROS_RIESGOSOS)


def resultado_parece_de_argentina(url, texto_resultado="", barrio=None):
    if url_tiene_indicios_argentina(url):
        return True

    if url_tiene_dominio_extranjero_riesgoso(url):
        return False

    if texto_tiene_indicios_extranjeros(texto_resultado):
        return False

    return texto_tiene_indicios_argentina(texto_resultado, barrio=barrio)


def web_parece_de_argentina(parroquia, url, html=""):
    texto_contexto = " ".join(
        [
            url or "",
            html[:20000] if html else "",
        ]
    )

    if url_tiene_indicios_argentina(url):
        return True

    if texto_tiene_indicios_argentina(texto_contexto, barrio=parroquia.barrio):
        return True

    if url_tiene_dominio_extranjero_riesgoso(url):
        return False

    if texto_tiene_indicios_extranjeros(texto_contexto):
        return False

    return False


def validar_web_de_argentina(parroquia, url, timeout=5):
    web = normalizar_url_web(url)

    if not web:
        return False

    if url_tiene_dominio_extranjero_riesgoso(web) and not url_tiene_indicios_argentina(web):
        return False

    try:
        response = requests.get(
            web,
            headers=HEADERS,
            timeout=timeout,
            allow_redirects=True,
        )
        if response.status_code != 200 or len(response.text) <= 500:
            return False

        return web_parece_de_argentina(parroquia, response.url or web, response.text)
    except Exception:
        return False


def enriquecer_webs():
    parroquias = Parroquia.objects.all()

    print(f"Total parroquias: {parroquias.count()}")

    for p in parroquias:
        print(f"\nProcesando: {p.nombre}")

        web_actual = p.sitio_web

        # 1. Si tiene web, validar
        if web_actual:
            if validar_web_de_argentina(p, web_actual):
                print("Web valida de Argentina")
                continue
            else:
                print("Web rota o sin indicios de Argentina, buscando nueva...")

        else:
            print("Sin web, buscando...")

        # 2. Buscar nueva web
        nueva_web = buscar_web(p.nombre, p.barrio or "")

        if nueva_web:
            print(f"Nueva web encontrada: {nueva_web}")

            p.sitio_web = nueva_web
            p.save()

        else:
            print("No se encontro web")

        time.sleep(1)


def normalizar_texto_comparacion(texto):
    if not texto:
        return ""

    texto = texto.lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.replace("-", " ").replace("_", " ")
    texto = re.sub(r"[^a-z0-9\s]", " ", texto)
    texto = re.sub(r"\s+", " ", texto)

    return texto.strip()


def normalizar_url_web(url):
    if not url:
        return None

    url = url.strip()
    if not url:
        return None

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    return url


def limpiar_url_social(url):
    parsed = urlparse(url.strip())
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc.lower()

    if netloc.startswith("www."):
        netloc = netloc[4:]

    path = parsed.path.rstrip("/")
    query = parse_qs(parsed.query, keep_blank_values=True)
    query_limpia = {
        key: values
        for key, values in query.items()
        if key.lower() not in IGNORED_QUERY_PARAMS
    }

    return urlunparse(
        (
            scheme,
            netloc,
            path,
            "",
            urlencode(query_limpia, doseq=True),
            "",
        )
    )


def obtener_tipo_por_dominio(netloc):
    dominio = netloc.lower()
    if dominio.startswith("www."):
        dominio = dominio[4:]

    for social_domain, tipo in SOCIAL_DOMAINS.items():
        if dominio == social_domain or dominio.endswith("." + social_domain):
            return tipo

    return None


def es_link_social_valido(tipo, parsed):
    path = parsed.path.lower()
    query = parsed.query.lower()

    if not path or path == "/":
        return False

    for excluded in EXCLUDED_PATH_PARTS.get(tipo, ()):
        if path.startswith(excluded) or excluded in path or excluded.strip("/") in query:
            return False

    return True


def extraer_username(tipo, url):
    parsed = urlparse(url)
    path_parts = [part for part in parsed.path.split("/") if part]

    if not path_parts:
        return None

    first = path_parts[0]

    if tipo == "facebook":
        if first in {"pages", "profile.php"}:
            return path_parts[1] if len(path_parts) > 1 else None
        return first

    if tipo == "instagram":
        return first

    if tipo == "youtube":
        if first.startswith("@"):
            return first
        if first in {"channel", "c", "user"} and len(path_parts) > 1:
            return path_parts[1]
        return first

    if tipo == "tiktok":
        return first if first.startswith("@") else None

    if tipo == "otro":
        return first

    return None


def detectar_red_social_desde_href(href, base_url):
    if not href:
        return None

    href = href.strip()
    if href.startswith(("mailto:", "tel:", "javascript:", "#")):
        return None

    url = urljoin(base_url, href)
    url = limpiar_url_social(url)
    parsed = urlparse(url)
    tipo = obtener_tipo_por_dominio(parsed.netloc)

    if not tipo:
        return None

    if not es_link_social_valido(tipo, parsed):
        return None

    username = extraer_username(tipo, url)

    return {
        "tipo": tipo,
        "url": url,
        "username": username,
    }


def extraer_redes_desde_html(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    redes = {}

    for link in soup.find_all("a", href=True):
        red = detectar_red_social_desde_href(link.get("href"), base_url)
        if not red:
            continue

        redes[red["url"]] = red

    return list(redes.values())


def es_red_probablemente_oficial(parroquia, red):
    username = red.get("username") or ""
    url = red.get("url") or ""
    texto_red = normalizar_texto_comparacion(f"{username} {url}")
    texto_red_sin_espacios = texto_red.replace(" ", "")

    if not texto_red:
        return False

    for termino in TERMINOS_GENERICOS_NO_OFICIALES:
        termino_normalizado = normalizar_texto_comparacion(termino)
        termino_sin_espacios = termino_normalizado.replace(" ", "")

        if termino_normalizado and termino_normalizado in texto_red:
            return False

        if termino_sin_espacios and termino_sin_espacios in texto_red_sin_espacios:
            return False

    if "parroquia" in texto_red.split() or "parroquia" in texto_red_sin_espacios:
        return True

    nombre_normalizado = normalizar_texto_comparacion(parroquia.nombre)
    tokens_nombre = [
        token
        for token in nombre_normalizado.split()
        if token not in PALABRAS_NO_SIGNIFICATIVAS and len(token) > 2
    ]

    if not tokens_nombre:
        return False

    tokens_red = set(texto_red.split())
    tokens_encontrados = {
        token
        for token in tokens_nombre
        if token in tokens_red or token in texto_red_sin_espacios
    }

    if len(tokens_encontrados) >= 2:
        return True

    for token in tokens_nombre:
        if len(token) > 5 and (token in tokens_red or token in texto_red_sin_espacios):
            return True

    return False


def guardar_redes(parroquia, redes):
    guardadas = []

    for red in redes:
        obj, created = RedSocial.objects.get_or_create(
            parroquia=parroquia,
            url=red["url"],
            defaults={
                "tipo": red["tipo"],
                "username": red["username"],
                "activo": True,
                "verificado": False,
            },
        )
        if not created:
            obj.tipo = red["tipo"]
            obj.username = red["username"]
            obj.activo = True
            obj.save(update_fields=["tipo", "username", "activo"])

        guardadas.append((obj, created))

    return guardadas


def desactivar_redes_obsoletas(parroquia, redes_validas):
    urls_validas = {red["url"] for red in redes_validas}
    redes_actuales = parroquia.redes.filter(activo=True)

    if urls_validas:
        redes_obsoletas = redes_actuales.exclude(url__in=urls_validas)
    else:
        redes_obsoletas = redes_actuales

    desactivadas = redes_obsoletas.update(activo=False)

    if desactivadas:
        print(f"Redes existentes marcadas como inactivas: {desactivadas}")

    return desactivadas


def analizar_web_parroquia(parroquia, timeout=TIMEOUT_RED_SOCIAL):
    web = normalizar_url_web(parroquia.sitio_web)

    if not web:
        print("Sin sitio_web. Se omite busqueda externa por ahora.")
        return []

    print(f"Web analizada: {web}")

    if url_tiene_dominio_extranjero_riesgoso(web) and not url_tiene_indicios_argentina(web):
        print("Web omitida por tener dominio extranjero sin indicios de Argentina.")
        return []

    response = requests.get(
        web,
        headers=HEADERS,
        timeout=timeout,
        allow_redirects=True,
    )
    response.raise_for_status()

    if not web_parece_de_argentina(parroquia, response.url or web, response.text):
        print("Web omitida porque no presenta indicios suficientes de Argentina.")
        return []

    return extraer_redes_desde_html(response.text, response.url or web)


def detectar_redes(
    limit=None,
    force=False,
    sleep=1,
    timeout=TIMEOUT_RED_SOCIAL,
    id_externo=None,
    nombre=None,
):
    parroquias = Parroquia.objects.all().order_by("id")

    if id_externo:
        parroquias = parroquias.filter(id_externo=id_externo)

    if nombre:
        parroquias = parroquias.filter(nombre__icontains=nombre)

    if limit:
        parroquias = parroquias[:limit]

    total = parroquias.count() if hasattr(parroquias, "count") else len(parroquias)
    stats = {
        "procesadas": 0,
        "saltadas": 0,
        "con_redes": 0,
        "sin_redes": 0,
        "guardadas": 0,
        "errores": 0,
    }

    print(f"Total parroquias a procesar: {total}")

    for parroquia in parroquias:
        print(f"\nProcesando parroquia: {parroquia.nombre}")

        try:
            if not force and (parroquia.redes.filter(activo=True).exists() or parroquia.tiene_redes):
                print(
                    "Ya tiene redes cargadas o tiene_redes=True. "
                    "Se salta. Use --force para reprocesar."
                )
                stats["saltadas"] += 1
                continue

            redes_detectadas = analizar_web_parroquia(parroquia, timeout=timeout)
            redes = []

            for red in redes_detectadas:
                if es_red_probablemente_oficial(parroquia, red):
                    redes.append(red)
                else:
                    print(
                        "Red omitida porque no parece corresponder a la parroquia: "
                        f"{red['tipo']} - {red['url']}"
                    )

            stats["procesadas"] += 1

            if force:
                desactivar_redes_obsoletas(parroquia, redes)

            if redes:
                print(
                    "Redes encontradas: "
                    + ", ".join(f"{red['tipo']} ({red['url']})" for red in redes)
                )
                guardadas = guardar_redes(parroquia, redes)
                stats["guardadas"] += len(guardadas)
                stats["con_redes"] += 1
                parroquia.tiene_redes = True
                parroquia.save(update_fields=["tiene_redes", "actualizado_el"])

                for red_social, created in guardadas:
                    accion = "creada" if created else "actualizada"
                    print(f"Red {accion}: {red_social.tipo} - {red_social.url}")
            else:
                print("No se encontraron redes oficiales en la web.")
                stats["sin_redes"] += 1
                parroquia.tiene_redes = False
                parroquia.save(update_fields=["tiene_redes", "actualizado_el"])

        except requests.exceptions.Timeout as exc:
            stats["errores"] += 1
            print(f"Timeout conectando con la web: {exc}")
        except requests.exceptions.ConnectionError as exc:
            stats["errores"] += 1
            print(f"Error de conexion: {exc}")
        except requests.exceptions.SSLError as exc:
            stats["errores"] += 1
            print(f"Error SSL: {exc}")
        except requests.exceptions.RequestException as exc:
            stats["errores"] += 1
            print(f"Error HTTP/request: {exc}")
        except Exception as exc:
            stats["errores"] += 1
            print(f"Error inesperado procesando parroquia: {exc}")

        if sleep:
            time.sleep(sleep)

    print("\nResumen final")
    print(f"Procesadas: {stats['procesadas']}")
    print(f"Saltadas: {stats['saltadas']}")
    print(f"Con redes: {stats['con_redes']}")
    print(f"Sin redes: {stats['sin_redes']}")
    print(f"Redes guardadas/actualizadas: {stats['guardadas']}")
    print(f"Errores: {stats['errores']}")

    return stats
